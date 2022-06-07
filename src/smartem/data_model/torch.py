from pathlib import Path
from typing import List, Sequence, Tuple

from torch import Tensor
from torch.utils.data import DataLoader
from torchvision.io import read_image

from smartem.data_model import EPUImage, FoilHole, GridSquare
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import (
    extract_keys_with_foil_hole_averages,
    extract_keys_with_grid_square_averages,
)


class SmartEMDataLoader(DataLoader):
    def __init__(
        self,
        level: str,
        epu_dir: Path,
        atlas_id: int,
        data_api: DataAPI,
        mrc: bool = False,
    ):
        self._data_api = data_api
        self._level = level
        self._epu_dir = epu_dir
        self._mrc = mrc
        atlas_info = self._data_api.get_atlas_info(
            atlas_id,
            ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
            [],
            ["_rlnestimatedresolution"],
        )
        if self._level not in ("grid_square", "foil_hole"):
            raise ValueError(
                f"Unrecognised SmartEMDataLoader level {self._level}: accepted values are grid_sqaure or foil_hole"
            )
        exposures = self._data_api.get_exposures()
        particles = self._data_api.get_particles()
        self._indexed: Sequence[EPUImage] = []
        if self._level == "grid_square":
            _, self._labels = extract_keys_with_grid_square_averages(
                atlas_info,
                ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
                [],
                ["_rlnestimatedresolution"],
                exposures,
                particles,
            )
            _gs_indexed: Sequence[GridSquare] = self._data_api.get_grid_squares()
            self._image_paths = {p.grid_square_name: p.thumbnail for p in _gs_indexed}
            self._indexed = _gs_indexed
        elif self._level == "foil_hole":
            _, self._labels = extract_keys_with_foil_hole_averages(
                atlas_info,
                ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
                [],
                ["_rlnestimatedresolution"],
                exposures,
                particles,
            )
            _fh_indexed: Sequence[FoilHole] = self._data_api.get_foil_holes()
            self._image_paths = {p.foil_hole_name: p.thumbnail for p in _fh_indexed}
            self._indexed = _fh_indexed

    def __len__(self) -> int:
        return len(self._image_paths)

    def __getitem__(self, idx: int) -> Tuple[Tensor, List[float]]:
        ordered_labels = [
            "_rlnaccummotiontotal",
            "_rlnctfmaxresolution",
            "_rlnestimatedresolution",
        ]
        if self._level == "grid_square":
            index_name = self._indexed[idx].grid_square_name  # type: ignore
        elif self._label == "foil_hole":
            index_name = self._indexed[idx].foil_hole_name  # type: ignore
        image = read_image(str(self._epu_dir / self._image_paths[index_name]))
        labels = [self._labels[l][index_name] for l in ordered_labels]
        return image, labels
