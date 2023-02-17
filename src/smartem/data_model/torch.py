import functools
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mrcfile
import numpy as np
import pandas as pd
import tifffile
import yaml
from PIL import Image
from torch import Tensor, from_numpy, reshape
from torch.utils.data import DataLoader
from torchvision.io import read_image

from smartem.data_model.extract import DataAPI
from smartem.parsing.epu import calibrate_coordinate_system
from smartem.parsing.export import get_dataframe
from smartem.stage_model import StageCalibration, find_point_pixel


@functools.lru_cache(maxsize=50)
def mrc_to_tensor(mrc_file: Path) -> Tensor:
    with mrcfile.open(mrc_file) as mrc:
        data = mrc.data
    shape = data.shape
    if data.dtype.char in np.typecodes["AllInteger"]:
        tensor_2d = Tensor(data.astype(np.int16))
    else:
        tensor_2d = Tensor(data.astype(np.float16))
    return reshape(tensor_2d, (1, shape[0], shape[1]))


@functools.lru_cache(maxsize=50)
def tiff_to_tensor(tiff_file: Path) -> Tensor:
    data = tifffile.imread(tiff_file)
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
        full_res: bool = False,
        num_samples: int = 0,
        sub_sample_size: Optional[Tuple[int, int]] = None,
        allowed_labels: Optional[Dict[str, bool]] = None,
        seed: int = 0,
    ):
        np.random.seed(seed)
        self._level = level
        self._use_full_res = full_res
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
                f"Unrecognised SmartEMDataLoader level {self._level}: accepted values are grid_square or foil_hole"
            )

        self._full_res_extension = ""
        self._data_dir = Path("/")
        self._df = pd.DataFrame()

    def _determine_extension(self):
        if Path(self._df.iloc[0]["grid_square"]).with_suffix(".mrc").exists():
            self._full_res_extension = ".mrc"
        elif Path(self._df.iloc[0]["grid_square"]).with_suffix(".tiff").exists():
            self._full_res_extension = ".tiff"
        elif Path(self._df.iloc[0]["grid_square"]).with_suffix(".tif").exists():
            self._full_res_extension = ".tif"
        else:
            self._full_res_extension = ""
        if self._level == "foil_hole":
            self._df = self._df[self._df["foil_hole"].notna()]
        if self._full_res_extension in (".tiff", ".tif"):
            tiff_file = (self._data_dir / self._df.iloc[0]["grid_square"]).with_suffix(
                self._full_res_extension
            )
            self._gs_full_res_size = tifffile.imread(tiff_file).shape
        else:
            with mrcfile.open(
                (self._data_dir / self._df.iloc[0]["grid_square"]).with_suffix(".mrc")
            ) as _mrc:
                self._gs_full_res_size = _mrc.data.shape
        with Image.open(self._data_dir / self._df.iloc[0]["grid_square"]) as im:
            self._gs_jpeg_size = im.size
        if self._use_full_res:
            self._boundary_points_x = np.random.randint(
                self._gs_full_res_size[1] - self._sub_sample_size[0], size=len(self)
            )
            self._boundary_points_y = np.random.randint(
                self._gs_full_res_size[0] - self._sub_sample_size[1], size=len(self)
            )
        else:
            self._boundary_points_x = np.random.randint(
                self._gs_jpeg_size[0] - self._sub_sample_size[0], size=len(self)
            )
            self._boundary_points_y = np.random.randint(
                self._gs_jpeg_size[1] - self._sub_sample_size[1], size=len(self)
            )

    def __len__(self) -> int:
        if self._level == "grid_square" and self._num_samples:
            return self._df[self._level].nunique() * self._num_samples
        return self._df[self._level].nunique()

    def __getitem__(self, idx: int) -> Tuple[Tensor, List[float]]:
        sub_sample_boundaries = (-1, -1)
        if self._level == "grid_square" and self._num_samples:
            sub_sample_boundaries = (
                self._boundary_points_x[idx],
                self._boundary_points_y[idx],
            )
            grid_square_idx = idx // self._num_samples
            _grid_squares = self._df["grid_square"].unique()
            selected_df = self._df[
                self._df["grid_square"] == _grid_squares[grid_square_idx]
            ]
            drop_indices = []
            if self._use_full_res:
                for ri, row in selected_df.iterrows():
                    fh_centre = find_point_pixel(
                        (
                            row["foil_hole_x"],
                            row["foil_hole_y"],
                        ),
                        (row["grid_square_x"], row["grid_square_y"]),
                        row["grid_square_pixel_size"],
                        (self._gs_full_res_size[1], self._gs_full_res_size[0]),
                        xfactor=-1 if self._stage_calibration.x_flip else 1,
                        yfactor=-1 if self._stage_calibration.y_flip else 1,
                    )
                    if self._stage_calibration.inverted:
                        fh_centre = (fh_centre[1], fh_centre[0])
                    if (
                        fh_centre[0] < sub_sample_boundaries[0]
                        or fh_centre[1] < sub_sample_boundaries[1]
                        or fh_centre[0]
                        > sub_sample_boundaries[0] + self._sub_sample_size[0]
                        or fh_centre[1]
                        > sub_sample_boundaries[1] + self._sub_sample_size[1]
                    ):
                        drop_indices.append(ri)
            else:
                for ri, row in selected_df.iterrows():
                    fh_centre = find_point_pixel(
                        (
                            row["foil_hole_x"],
                            row["foil_hole_y"],
                        ),
                        (row["grid_square_x"], row["grid_square_y"]),
                        row["grid_square_pixel_size"]
                        * (self._gs_full_res_size[1] / self._gs_jpeg_size[0]),
                        self._gs_jpeg_size,
                        xfactor=-1 if self._stage_calibration.x_flip else 1,
                        yfactor=-1 if self._stage_calibration.y_flip else 1,
                    )
                    if self._stage_calibration.inverted:
                        fh_centre = (fh_centre[1], fh_centre[0])
                    if (
                        fh_centre[0] < sub_sample_boundaries[0]
                        or fh_centre[1] < sub_sample_boundaries[1]
                        or fh_centre[0]
                        > sub_sample_boundaries[0] + self._sub_sample_size[0]
                        or fh_centre[1]
                        > sub_sample_boundaries[1] + self._sub_sample_size[1]
                    ):
                        drop_indices.append(ri)
            selected_df = selected_df.drop(drop_indices)
            averaged_df = selected_df.groupby("grid_square").mean()
            if len(averaged_df):
                labels = [
                    v
                    for k, v in averaged_df.iloc[0].to_dict().items()
                    if k in self._allowed_labels
                ]
            else:
                labels = [np.inf if b else -np.inf for b in self._lower_better_label]
            if self._use_full_res:
                if self._full_res_extension == ".mrc":
                    preimage = mrc_to_tensor(
                        (self._data_dir / _grid_squares[grid_square_idx]).with_suffix(
                            ".mrc"
                        )
                    )
                elif self._full_res_extension in (".tiff", ".tif"):
                    preimage = tiff_to_tensor(
                        (self._data_dir / _grid_squares[grid_square_idx]).with_suffix(
                            self._full_res_extension
                        )
                    )
                image = preimage[
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
            if self._full_res_extension == ".mrc":
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
            if self._use_full_res:
                if self._full_res_extension == ".mrc":
                    image = mrc_to_tensor(
                        (self._data_dir / self._df.iloc[idx][self._level]).with_suffix(
                            ".mrc"
                        )
                    )
                elif self._full_res_extension in (".tiff", ".tif"):
                    image = tiff_to_tensor(
                        (self._data_dir / self._df.iloc[idx][self._level]).with_suffix(
                            self._full_res_extension
                        )
                    )
            else:
                image = read_image(
                    str(self._data_dir / self._df.iloc[idx][self._level])
                )
        return image, labels

    def thresholds(self, quantile: float = 0.7):
        required_columns = (
            [*_standard_labels, self._level]
            if self._level == "grid_square"
            else list(_standard_labels)
        )
        if self._level == "grid_square":
            newdf = (
                self._df[required_columns]
                .groupby(self._level)
                .mean()[list(_standard_labels)]
            )
        else:
            newdf = self._df[required_columns]
        return newdf.quantile(q=quantile)


class SmartEMPostgresDataLoader(SmartEMDataLoader):
    def __init__(
        self,
        level: str,
        projects: List[str],
        data_api: Optional[DataAPI] = None,
        **kwargs,
    ):
        super().__init__(level, **kwargs)
        self._data_api: DataAPI = data_api or DataAPI()
        self._df = get_dataframe(self._data_api, projects)
        super()._determine_extension()

        _project = self._data_api.get_project(project_name=projects[0])
        for dm in (Path(_project.acquisition_directory).parent / "Metadata").glob(
            "*.dm"
        ):
            self._stage_calibration = calibrate_coordinate_system(dm)
            if self._stage_calibration:
                break


_standard_labels = {
    "accummotiontotal": True,
    "ctfmaxresolution": True,
    "estimatedresolution": True,
    "maxvalueprobdistribution": False,
}


class SmartEMDiskDataLoader(SmartEMDataLoader):
    def __init__(
        self,
        level: str,
        data_dir: Path,
        full_res: bool = False,
        labels_csv: str = "labels.csv",
        num_samples: int = 0,
        sub_sample_size: Optional[Tuple[int, int]] = None,
        allowed_labels: Optional[Dict[str, bool]] = None,
        seed: int = 0,
    ):
        super().__init__(
            level,
            full_res=full_res,
            num_samples=num_samples,
            sub_sample_size=sub_sample_size,
            allowed_labels=allowed_labels,
            seed=seed,
        )
        self._data_dir = data_dir
        self._df = pd.read_csv(self._data_dir / labels_csv)
        super()._determine_extension()

        try:
            with open(self._data_dir / "coordinate_calibration.yaml", "r") as cal_in:
                sc = yaml.safe_load(cal_in)
        except FileNotFoundError:
            sc = {"inverted": False, "x_flip": False, "y_flip": True}
        self._stage_calibration = StageCalibration(**sc)


class SmartEMMaskDataLoader(DataLoader):
    def __init__(self, data_dir: Path, labels_csv: str = "labels.csv"):
        self._data_dir = data_dir
        self._df = (
            pd.read_csv(self._data_dir / labels_csv).groupby("grid_square").mean()
        )
        if (self._data_dir / self._df.iloc[0].name).with_suffix(".mrc").exists():
            self._full_res_extension = ".mrc"
        elif (self._data_dir / self._df.iloc[0].name).with_suffix(".tiff").exists():
            self._full_res_extension = ".tiff"
        elif (self._data_dir / self._df.iloc[0].name).with_suffix(".tif").exists():
            self._full_res_extension = ".tif"
        else:
            raise FileNotFoundError(
                f"{self._data_dir / self._df.iloc[0].name} was not found with any of the following suffixes: .mrc, .tiff, .tif"
            )

    def __len__(self) -> int:
        return len(self._df.index)

    def __getitem__(self, idx: int) -> Tuple[Tensor, Tensor]:
        image_path = (self._data_dir / self._df.iloc[idx].name).with_suffix(
            self._full_res_extension
        )
        if self._full_res_extension == ".mrc":
            image = mrc_to_tensor(image_path)
        else:
            image = tiff_to_tensor(image_path)
        mask = from_numpy(np.load(image_path.with_suffix(".npy")))
        return image, mask
