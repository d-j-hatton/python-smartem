import functools
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mrcfile
import numpy as np
import pandas as pd
import tifffile
import yaml
from PIL import Image
from torch import Tensor, from_numpy, reshape
from torch.utils.data import Dataset
from torchvision.io import read_image
from torchvision.transforms import Compose

from smartem.data_model import PhysicalSubset
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
    tensor_2d = (tensor_2d - tensor_2d.min()) * (255.0 / tensor_2d.max())
    tensor_2d = Tensor(tensor_2d.detach().cpu().numpy().astype(np.uint8))
    return reshape(tensor_2d, (1, shape[0], shape[1])).repeat(3, 1, 1)


@functools.lru_cache(maxsize=50)
def tiff_to_tensor(tiff_file: Path) -> Tensor:
    data = tifffile.imread(tiff_file)
    shape = data.shape
    if data.dtype.char in np.typecodes["AllInteger"]:
        tensor_2d = Tensor(data.astype(np.int16))
    else:
        tensor_2d = Tensor(data.astype(np.float16))
    tensor_2d = (tensor_2d - tensor_2d.min()) * (255.0 / tensor_2d.max())
    tensor_2d = Tensor(tensor_2d.detach().cpu().numpy().astype(np.uint8))
    return reshape(tensor_2d, (1, shape[0], shape[1])).repeat(3, 1, 1)


class SmartEMDataset(Dataset):
    def __init__(
        self,
        name: str,
        level: str,
        full_res: bool = False,
        num_samples: int = 0,
        sub_sample_size: Optional[Tuple[int, int]] = None,
        physical_sub_sample_size: Optional[PhysicalSubset] = None,
        allowed_labels: Optional[Dict[str, bool]] = None,
        transform: Optional[Compose] = None,
        restricted_indices: Optional[List[int]] = None,
        seed: int = 0,
        dataframe: Optional[pd.DataFrame] = None,
        boundary_points: Optional[List[Tuple[int, int]]] = None,
    ):
        np.random.seed(seed)
        self.name = name
        self._level = level
        self._use_full_res = full_res
        self._num_samples = num_samples
        if physical_sub_sample_size:
            self._sub_sample_size = (
                int(
                    physical_sub_sample_size.sub_sample_size[0]
                    / physical_sub_sample_size.pixel_sizes[self._level]
                ),
                int(
                    physical_sub_sample_size.sub_sample_size[1]
                    / physical_sub_sample_size.pixel_sizes[self._level]
                ),
            )
        else:
            self._sub_sample_size = sub_sample_size or (256, 256)
        self._allowed_labels = allowed_labels or list(_standard_labels.keys())
        self._restricted_indices = restricted_indices or []
        self._transform = transform or Compose([])
        self._lower_better_label = (
            [allowed_labels[k] for k in self._allowed_labels]
            if allowed_labels
            else [_standard_labels[k] for k in self._allowed_labels]
        )
        if self._level not in ("grid_square", "foil_hole"):
            raise ValueError(
                f"Unrecognised SmartEMDataset level {self._level}: accepted values are grid_square or foil_hole"
            )

        self._full_res_extension = ""
        self._data_dir = Path("/")
        self._df = pd.DataFrame() if dataframe is None else dataframe
        self._saved_thresholds: pd.DataFrame | None = None
        self._boundary_points_x = (
            [b[0] for b in boundary_points] if boundary_points else []
        )
        self._boundary_points_y = (
            [b[1] for b in boundary_points] if boundary_points else []
        )

    @classmethod
    def restrict_indices(cls, restricted_indices: List[int], base: "SmartEMDataset"):
        return cls(
            base.name,
            base._level,
            full_res=base._use_full_res,
            num_samples=base._num_samples,
            sub_sample_size=base._sub_sample_size,
            allowed_labels={
                k: k in base._lower_better_label for k in base._allowed_labels
            },
            transform=base._transform,
            restricted_indices=restricted_indices,
            dataframe=base._df,
            boundary_points=[
                (bx, by)
                for i, (bx, by) in enumerate(
                    zip(base._boundary_points_x, base._boundary_points_y)
                )
                if i in restricted_indices
            ],
        )

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
        if not self._boundary_points_x:
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
        if self._restricted_indices:
            return len(self._restricted_indices)
        if self._level == "grid_square" and self._num_samples:
            return self._df[self._level].nunique() * self._num_samples
        return self._df[self._level].nunique()

    def __getitem__(self, idx: int) -> Tuple[Tensor, int]:
        if self._restricted_indices:
            idx = self._restricted_indices[idx]
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
            averaged_df = selected_df.groupby("grid_square").mean(numeric_only=True)
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

        label = self.compute_label(image, annotations=labels)
        if self._transform:
            image = self._transform(image)
            image = (image - image.min()) / image.max()
        return self._transform(image), label

    def split_indices(
        self,
        equal_label_populations: bool = True,
        probs_per_set: Dict[str, float] = {"train": 0.8, "val": 0.1, "test": 0.1},
    ) -> Dict[str, List[int]]:
        data_set_names = []
        probs = []
        for k, v in probs_per_set.items():
            data_set_names.append(k)
            probs.append(v)
        selected_indices: Dict[str, List[int]] = {dn: [] for dn in data_set_names}
        label_counts = None
        if equal_label_populations:
            label_counts = Counter([p[1] for p in self])
            assigned_label_counts = {k: 0 for k in label_counts.keys()}
        for i in range(len(self)):
            if self[i][1] < 2:
                if label_counts:
                    if assigned_label_counts[self[i][1]] <= min(label_counts.values()):
                        data_set = np.random.choice(data_set_names, p=probs)
                        selected_indices[data_set].append(i)
                        assigned_label_counts[self[i][1]] += 1
                else:
                    data_set = np.random.choice(data_set_names, p=probs)
                    selected_indices[data_set].append(i)
        return selected_indices

    def compute_label(
        self,
        image: Tensor,
        annotations: List[float],
        sigmas: Optional[Dict[str, float]] = None,
    ) -> int:
        imdata = image.detach().numpy()[0]
        pixel_condition = len(imdata[imdata > 60]) / (image.shape[1] * image.shape[2])
        sigmas = sigmas or {
            "accummotiontotal": 1,
            "ctfmaxresolution": 0.4,
            "particlecount": 0.5,
            "estimatedresolution": 1,
            "maxvalueprobdistribution": -0.75,
        }
        ths = self.thresholds(sigmas=sigmas)
        labels = [(k, v) for k, v in _standard_labels.items()]
        if np.inf in annotations:
            return 3
        conds = [
            annotations[i] < ths[labels[i][0]].iloc[0]
            if labels[i][1]
            else annotations[i] > ths[labels[i][0]].iloc[0]
            for i in range(len(annotations))
        ]
        if pixel_condition < 0.5:
            return 3
        if sum(conds) == len(labels):
            return 0
        if sum(conds) < len(labels) // 2:
            return 1
        return 3

    def thresholds(
        self,
        quantile: float = 0.7,
        sigmas: Optional[Dict[str, float]] = None,
        refresh: bool = False,
    ):
        if self._saved_thresholds is not None and not refresh:
            return self._saved_thresholds
        required_columns = [*_standard_labels, self._level]
        newdf = self._df[required_columns]
        if sigmas:
            res = pd.DataFrame(
                {k: [newdf[k].mean() + q * newdf[k].std()] for k, q in sigmas.items()}
            )
            self._saved_thresholds = res
            return res
        res = newdf.quantile(q=quantile)
        self._saved_thresholds = res
        return res


class SmartEMMultiDataset(Dataset):
    def __init__(self, *args: SmartEMDataset):
        self._datasets = {d.name: d for d in args}
        self._dataset_order = list(self._datasets.keys())

    def _get_key_idx(self, idx: int) -> Tuple[str, int]:
        rolling_sum = 0
        for kd in self._dataset_order:
            next_rolling_sum = rolling_sum + len(self._datasets[kd])
            if idx >= rolling_sum and idx < next_rolling_sum:
                return (kd, idx - rolling_sum)
            rolling_sum = next_rolling_sum
        raise IndexError(f"Index {idx} out of range {len(self)}")

    def __len__(self):
        return sum(len(d) for d in self._datasets.values())

    def __getitem__(self, idx: int):
        dataset_key, dataset_idx = self._get_key_idx(idx)
        return self._datasets[dataset_key][dataset_idx]


class SmartEMPostgresDataset(SmartEMDataset):
    def __init__(
        self,
        name: str,
        level: str,
        projects: List[str],
        data_api: Optional[DataAPI] = None,
        **kwargs,
    ):
        super().__init__(name, level, **kwargs)
        self._projects = projects
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

    @classmethod
    def restrict_indices(cls, restricted_indices: List[int], base: "SmartEMDataset"):
        return cls(
            base.name,
            base._level,
            base._projects,
            full_res=base._use_full_res,
            num_samples=base._num_samples,
            sub_sample_size=base._sub_sample_size,
            allowed_labels={
                k: k in base._lower_better_label for k in base._allowed_labels
            },
            transform=base._transform,
            restricted_indices=restricted_indices,
            dataframe=base._df,
            boundary_points=[
                (bx, by)
                for (bx, by) in (zip(base._boundary_points_x, base._boundary_points_y))
            ],
        )


_standard_labels = {
    "accummotiontotal": True,
    "ctfmaxresolution": True,
    "particlecount": False,
    "estimatedresolution": True,
    "maxvalueprobdistribution": False,
}


class SmartEMDiskDataset(SmartEMDataset):
    def __init__(
        self,
        name: str,
        level: str,
        data_dir: Path,
        full_res: bool = False,
        labels_csv: str = "labels.csv",
        num_samples: int = 0,
        sub_sample_size: Optional[Tuple[int, int]] = None,
        physical_sub_sample_size: Optional[PhysicalSubset] = None,
        transform: Optional[Compose] = None,
        allowed_labels: Optional[Dict[str, bool]] = None,
        restricted_indices: Optional[List[int]] = None,
        seed: int = 0,
        dataframe: Optional[pd.DataFrame] = None,
        boundary_points: Optional[List[Tuple[int, int]]] = None,
    ):
        super().__init__(
            name,
            level,
            full_res=full_res,
            num_samples=num_samples,
            sub_sample_size=sub_sample_size,
            physical_sub_sample_size=physical_sub_sample_size,
            transform=transform,
            allowed_labels=allowed_labels,
            restricted_indices=restricted_indices,
            seed=seed,
            boundary_points=boundary_points,
        )
        self._data_dir = data_dir
        if dataframe:
            self._df = dataframe
        else:
            self._df = pd.read_csv(self._data_dir / labels_csv)
            self._df["grid_square"] = f"{self._data_dir}/" + self._df[
                "grid_square"
            ].astype(str)
        super()._determine_extension()

        try:
            with open(self._data_dir / "coordinate_calibration.yaml", "r") as cal_in:
                sc = yaml.safe_load(cal_in)
        except FileNotFoundError:
            sc = {"inverted": False, "x_flip": False, "y_flip": True}
        self._stage_calibration = StageCalibration(**sc)

    @classmethod
    def restrict_indices(cls, restricted_indices: List[int], base: "SmartEMDataset"):
        return cls(
            base.name,
            base._level,
            base._data_dir,
            full_res=base._use_full_res,
            num_samples=base._num_samples,
            sub_sample_size=base._sub_sample_size,
            allowed_labels={
                k: k in base._lower_better_label for k in base._allowed_labels
            },
            transform=base._transform,
            restricted_indices=restricted_indices,
            dataframe=base._df,
            boundary_points=[
                (bx, by)
                for (bx, by) in (zip(base._boundary_points_x, base._boundary_points_y))
            ],
        )


class SmartEMMaskDataset(Dataset):
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
