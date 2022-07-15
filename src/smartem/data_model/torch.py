from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import mrcfile
import numpy as np
import pandas as pd
from PIL import Image
from torch import Tensor, reshape, zeros
from torch.utils.data import DataLoader
from torchvision.io import read_image

from smartem.data_model import EPUImage, FoilHole, GridSquare
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import (
    extract_keys_with_foil_hole_averages,
    extract_keys_with_grid_square_averages,
)
from smartem.stage_model import find_point_pixel


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
        project: str,
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
        self._indexed: Sequence[EPUImage] = []
        if self._level == "grid_square":
            _labels = extract_keys_with_grid_square_averages(
                atlas_info,
                ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
                [],
                ["_rlnestimatedresolution"],
            )
            self._labels = {k: v.averages for k, v in _labels.items() if v.averages}
            _gs_indexed: Sequence[GridSquare] = self._data_api.get_grid_squares(
                project=project
            )
            self._image_paths = {
                p.grid_square_name: p.thumbnail
                for p in _gs_indexed
                if p.grid_square_name
            }
            self._indexed = _gs_indexed
        elif self._level == "foil_hole":
            _labels = extract_keys_with_foil_hole_averages(
                atlas_info,
                ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
                [],
                ["_rlnestimatedresolution"],
            )
            self._labels = {k: v.averages for k, v in _labels.items() if v.averages}
            _fh_indexed: Sequence[FoilHole] = self._data_api.get_foil_holes()
            self._image_paths = {
                p.foil_hole_name: p.thumbnail for p in _fh_indexed if p.foil_hole_name
            }
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
        img_path = self._image_paths[index_name]
        if img_path:
            if self._mrc:
                image = mrc_to_tensor((self._epu_dir / img_path).with_suffix(".mrc"))
            else:
                image = read_image(str(self._epu_dir / img_path))
            labels = [self._labels[l][index_name] for l in ordered_labels]
        else:
            image = zeros(1, 512, 512)
        return image, labels


_standard_labels = {
    "accummotiontotal": True,
    "ctfmaxresolution": True,
    "estimatedresolution": True,
    "maxvalueprobdistribution": False,
}


class SmartEMDiskDataLoader(DataLoader):
    def __init__(
        self,
        level: str,
        data_dir: Path,
        mrc: bool = False,
        labels_csv: str = "labels.csv",
        num_samples: int = 0,
        sub_sample_size: Optional[Tuple[int, int]] = None,
        allowed_labels: Optional[Dict[str, bool]] = None,
        seed: int = 0,
    ):
        np.random.seed(seed)
        self._level = level
        self._data_dir = data_dir
        self._mrc = mrc
        self._num_samples = num_samples
        self._sub_sample_size = sub_sample_size or (256, 256)
        self._allowed_labels = allowed_labels or list(_standard_labels.keys())
        self._lower_better_label = (
            [allowed_labels[k] for k in self._allowed_labels]
            if allowed_labels
            else [_standard_labels[k] for k in self._allowed_labels]
        )
        if self._level not in ("grid_square", "foil_hole"):
            raise ValueError(
                f"Unrecognised SmartEMDataLoader level {self._level}: accepted values are grid_sqaure or foil_hole"
            )
        self._df = pd.read_csv(self._data_dir / labels_csv)
        with mrcfile.open(
            (self._data_dir / self._df.iloc[0]["grid_square"]).with_suffix(".mrc")
        ) as _mrc:
            self._gs_mrc_size = _mrc.data.shape
        with Image.open(self._data_dir / self._df.iloc[0]["grid_square"]) as im:
            self._gs_jpeg_size = im.size
        for row in self._df:
            try:
                with mrcfile.open(
                    (self._data_dir / self._df.iloc[0]["foil_hole"]).with_suffix(".mrc")
                ) as _mrc:
                    self._fh_mrc_size = _mrc.data.shape
                with Image.open(self._data_dir / self._df.iloc[0]["foil_hole"]) as im:
                    self._fh_jpeg_size = im.size
                break
            except TypeError:
                continue

    def __len__(self) -> int:
        if self._level == "grid_square" and self._num_samples:
            return self._df[self._level].nunique() * self._num_samples
        return self._df[self._level].nunique()

    def __getitem__(self, idx: int) -> Tuple[Tensor, List[float]]:
        sub_sample_boundaries = (-1, -1)
        if self._level == "grid_square" and self._num_samples:
            if self._mrc:
                sub_sample_boundaries = (
                    np.random.randint(self._gs_mrc_size[1] - self._sub_sample_size[0]),
                    np.random.randint(self._gs_mrc_size[0] - self._sub_sample_size[1]),
                )
            else:
                sub_sample_boundaries = (
                    np.random.randint(self._gs_jpeg_size[0] - self._sub_sample_size[0]),
                    np.random.randint(self._gs_jpeg_size[1] - self._sub_sample_size[1]),
                )
            grid_square_idx = idx // self._num_samples
            _grid_squares = self._df["grid_square"].unique()
            selected_df = self._df[
                self._df["grid_square"] == _grid_squares[grid_square_idx]
            ]
            drop_indices = []
            if self._mrc:
                for ri, row in selected_df.iterrows():
                    # print(ri, len(selected_df))
                    fh_centre = find_point_pixel(
                        (
                            row["foil_hole_x"],
                            row["foil_hole_y"],
                        ),
                        (row["grid_square_x"], row["grid_square_y"]),
                        row["grid_square_pixel_size"],
                        (self._gs_mrc_size[1], self._gs_mrc_size[0]),
                        xfactor=1,
                        yfactor=-1,
                    )
                    if (
                        fh_centre[0] < sub_sample_boundaries[0]
                        or fh_centre[1] < sub_sample_boundaries[1]
                        or fh_centre[0]
                        > sub_sample_boundaries[0] + self._sub_sample_size[0]
                        or fh_centre[1]
                        > sub_sample_boundaries[1] + self._sub_sample_size[1]
                    ):
                        drop_indices.append(ri)  # selected_df.index[ri])
            else:
                for ri, row in selected_df.iterrows():
                    fh_centre = find_point_pixel(
                        (
                            row["foil_hole_x"],
                            row["foil_hole_y"],
                        ),
                        (row["grid_square_x"], row["grid_square_y"]),
                        row["grid_square_pixel_size"]
                        * (self._gs_mrc_size[1] / self._gs_jpeg_size[0]),
                        self._gs_jpeg_size,
                        xfactor=1,
                        yfactor=-1,
                    )
                    if (
                        fh_centre[0] < sub_sample_boundaries[0]
                        or fh_centre[1] < sub_sample_boundaries[1]
                        or fh_centre[0]
                        > sub_sample_boundaries[0] + self._sub_sample_size[0]
                        or fh_centre[1]
                        > sub_sample_boundaries[1] + self._sub_sample_size[1]
                    ):
                        drop_indices.append(ri)  # selected_df.index[ri])
            selected_df = selected_df.drop(drop_indices)
            print(selected_df)
            averaged_df = selected_df.groupby("grid_square").mean()
            if len(averaged_df):
                labels = [
                    v
                    for k, v in averaged_df.iloc[0].to_dict().items()
                    if k in self._allowed_labels
                ]
            else:
                labels = [np.inf if b else -np.inf for b in self._lower_better_label]
            if self._mrc:
                image = mrc_to_tensor(
                    (self._data_dir / _grid_squares[grid_square_idx]).with_suffix(
                        ".mrc"
                    )
                )[
                    :,
                    sub_sample_boundaries[1] : sub_sample_boundaries[1]
                    + self._sub_sample_size[1],
                    sub_sample_boundaries[0] : sub_sample_boundaries[0]
                    + self._sub_sample_size[0],
                ]
            else:
                image = read_image(
                    str(self._data_dir / _grid_squares[grid_square_idx])
                )[
                    :,
                    sub_sample_boundaries[1] : sub_sample_boundaries[1]
                    + self._sub_sample_size[1],
                    sub_sample_boundaries[0] : sub_sample_boundaries[0]
                    + self._sub_sample_size[0],
                ]
        elif self._level == "grid_square":
            averaged_df = self._df.groupby("grid_square").mean()
            labels = [
                v
                for k, v in averaged_df.iloc[idx].to_dict().items()
                if k in self._allowed_labels
            ]
            if self._mrc:
                image = mrc_to_tensor(
                    (self._data_dir / averaged_df.iloc[idx].name).with_suffix(".mrc")
                )
            else:
                image = read_image(str(self._data_dir / averaged_df.iloc[idx].name))
        else:
            labels = [
                v
                for k, v in self._df.iloc[idx].to_dict().items()
                if k in self._allowed_labels
            ]
            if self._mrc:
                image = mrc_to_tensor(
                    (self._data_dir / self._df.iloc[idx][self._level]).with_suffix(
                        ".mrc"
                    )
                )
            else:
                image = read_image(
                    str(self._data_dir / self._df.iloc[idx][self._level])
                )
        return image, labels
