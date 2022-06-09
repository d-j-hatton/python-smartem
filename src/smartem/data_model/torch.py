from pathlib import Path
from typing import List, Sequence, Tuple

import mrcfile
import numpy as np
import pandas as pd
from torch import Tensor, reshape
from torch.utils.data import DataLoader
from torchvision.io import read_image

from smartem.data_model import EPUImage, FoilHole, GridSquare
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import (
    extract_keys_with_foil_hole_averages,
    extract_keys_with_grid_square_averages,
)


def mrc_to_tensor(mrc_file: Path) -> Tensor:
    with mrcfile.open(mrc_file) as mrc:
        data = mrc.data
    shape = data.shape
    if data.dtype.char in np.typecodes["AllInteger"]:
        tensor_2d = Tensor(data.astype(np.int16))
    else:
        tensor_2d = Tensor(data.astype(np.float16))
    return reshape(tensor_2d, (1, shape[0], shape[1]))


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
        if self._mrc:
            image = mrc_to_tensor(
                (self._epu_dir / self._image_paths[index_name]).with_suffix(".mrc")
            )
        else:
            image = read_image(str(self._epu_dir / self._image_paths[index_name]))
        labels = [self._labels[l][index_name] for l in ordered_labels]
        return image, labels


class SmartEMDiskDataLoader(DataLoader):
    def __init__(
        self,
        level: str,
        data_dir: Path,
        mrc: bool = False,
        labels_csv: str = "labels.csv",
    ):
        self._level = level
        self._data_dir = data_dir
        self._mrc = mrc
        if self._level not in ("grid_square", "foil_hole"):
            raise ValueError(
                f"Unrecognised SmartEMDataLoader level {self._level}: accepted values are grid_sqaure or foil_hole"
            )
        self._df = pd.read_csv(self._data_dir / labels_csv)

    def __len__(self) -> int:
        return self._df[self._level].nunique()

    def __getitem__(self, idx: int) -> Tuple[Tensor, List[float]]:
        if self._mrc:
            image = mrc_to_tensor(
                (self._data_dir / self._df.iloc[idx][self._level]).with_suffix(".mrc")
            )
        else:
            image = read_image(str(self._data_dir / self._df.iloc[idx][self._level]))
        if self._level == "grid_square":
            averaged_df = self._df.groupby("grid_square").mean()
            labels = averaged_df.iloc[idx].to_list()
        else:
            labels = self._df.iloc[idx, 2:].to_list()
        return image, labels
