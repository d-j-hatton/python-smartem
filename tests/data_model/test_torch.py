import os
from unittest import mock

import mrcfile
import numpy as np
import pandas as pd
import pytest
import tifffile
from torch import Tensor

from smartem.data_model import torch


class TestSmartEMDataLoader:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.test_loader = torch.SmartEMDataLoader(
            level="grid_square",
            full_res=True,
            num_samples=2,
            sub_sample_size=(1, 1),
            allowed_labels={"test": True},
            seed=0,
        )

        # place grid square data in the data frame
        self.test_loader._df = pd.DataFrame(
            data={
                "grid_square": np.arange(10),
                "accummotiontotal": np.arange(10),
                "estimatedresolution": np.arange(10),
                "maxvalueprobdistribution": np.arange(10),
                "ctfmaxresolution": np.arange(10),
                "foil_hole_x": 0.1 * np.ones(10),
                "foil_hole_y": 0.2 * np.ones(10),
                "grid_square_x": 0.1 * np.ones(10),
                "grid_square_y": 0.2 * np.ones(10),
                "grid_square_pixel_size": 3 * np.ones(10),
            }
        )

    def test_determine_extension_mrc(self, tmp_path):
        """Check that the extension can be determined for a mrc file"""
        # make image files expected by loader
        mrcfile.write(
            tmp_path / "grid0.mrc",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
        )
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        self.test_loader._df["grid_square"] = [tmp_path / "grid0.tif"] * 10

        self.test_loader._determine_extension()

        # check the extension has been determined and the file size read in
        assert self.test_loader._full_res_extension == ".mrc"
        assert self.test_loader._gs_full_res_size == (2, 2)
        assert type(self.test_loader._boundary_points_x[0]) == np.int64
        assert type(self.test_loader._boundary_points_y[0]) == np.int64

    def test_determine_extension_tif(self, tmp_path):
        """Check that the extension can be determined for a tif file"""
        # make image files expected by loader
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        self.test_loader._df["grid_square"] = [tmp_path / "grid0.tif"] * 10

        self.test_loader._determine_extension()

        # check the extension has been determined and the file size read in
        assert self.test_loader._full_res_extension == ".tif"
        assert self.test_loader._gs_full_res_size == (2, 2)
        assert type(self.test_loader._boundary_points_x[0]) == np.int64
        assert type(self.test_loader._boundary_points_y[0]) == np.int64

    def test_len(self):
        # assert the length can be returned using len
        assert len(self.test_loader) == 20

    def test_get_item_grid_square(self, tmp_path):
        # make image files expected by loader
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        self.test_loader._df["grid_square"] = [tmp_path / "grid0.tif"] * 10

        # need to determine the extension before getting the item
        self.test_loader._stage_calibration = mock.MagicMock()
        self.test_loader._determine_extension()

        # assert the first value from the grid is returned and calibration is found
        assert self.test_loader[0] == (Tensor([[[110.0]]]), [])
        self.test_loader._stage_calibration.x_flip.__bool__.assert_called()
        self.test_loader._stage_calibration.y_flip.__bool__.assert_called()
        self.test_loader._stage_calibration.inverted.__bool__.assert_called()

    def test_get_item_no_samples(self, tmp_path):
        # make image files expected by loader and set to have no samples
        mrcfile.write(
            tmp_path / "grid0.mrc",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
        )
        self.test_loader._num_samples = 0
        self.test_loader._full_res_extension = ".mrc"
        self.test_loader._df["grid_square"] = [tmp_path / "grid0.mrc"] * 10

        # assert the grid tiff results are stored
        return_value = self.test_loader[0]
        assert return_value[0][0][0, 0] == 110
        assert return_value[0][0][0, 1] == 120
        assert return_value[0][0][1, 0] == 130
        assert return_value[0][0][1, 1] == 140
        assert return_value[1] == []

    def test_get_item_foil_hole(self, tmp_path):
        # make image files expected by loader and set to use foil hole
        tifffile.imwrite(
            tmp_path / "foil0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        self.test_loader._level = "foil_hole"
        self.test_loader._full_res_extension = ".tif"
        self.test_loader._df["foil_hole"] = [tmp_path / "foil0.tif"] * 10

        # assert the grid tiff results are stored
        return_value = self.test_loader[0]
        assert return_value[0][0][0, 0] == 110
        assert return_value[0][0][0, 1] == 120
        assert return_value[0][0][1, 0] == 130
        assert return_value[0][0][1, 1] == 140
        assert return_value[1] == []

    def test_thresholds(self):
        return_value = self.test_loader.thresholds(quantile=0.7)

        # assert that the quantiles are correct for each column
        assert return_value["accummotiontotal"] == 6.3
        assert return_value["estimatedresolution"] == 6.3
        assert return_value["maxvalueprobdistribution"] == 6.3
        assert return_value["ctfmaxresolution"] == 6.3


class TestSmartEMPostgresDataLoader:
    @mock.patch("smartem.data_model.torch.get_dataframe")
    @mock.patch("smartem.data_model.torch.calibrate_coordinate_system")
    def test_postgres_data_loader(self, mock_calibrate, mock_get_dataframe, tmp_path):
        mock_api = mock.MagicMock()
        mock_api.get_project().acquisition_directory = tmp_path

        # grid square data which would be read from a database
        mock_get_dataframe.return_value = pd.DataFrame(
            data={
                "grid_square": [tmp_path / "grid0.tif"] * 10,
                "accummotiontotal": np.arange(10),
                "estimatedresolution": np.arange(10),
                "maxvalueprobdistribution": np.arange(10),
                "ctfmaxresolution": np.arange(10),
                "foil_hole_x": 0.1 * np.ones(10),
                "foil_hole_y": 0.2 * np.ones(10),
                "grid_square_x": 0.1 * np.ones(10),
                "grid_square_y": 0.2 * np.ones(10),
                "grid_square_pixel_size": 3 * np.ones(10),
            }
        )

        # make image files expected by loader
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        try:
            os.mkdir(tmp_path / "../Metadata")
        except FileExistsError:
            pass
        with open(tmp_path / "../Metadata/grid_test.dm", "w") as f:
            f.write("dummy")

        # run the loader
        self.test_loader = torch.SmartEMPostgresDataLoader(
            level="grid_square",
            projects=["test"],
            data_api=mock_api,
            full_res=True,
            num_samples=2,
            sub_sample_size=(1, 1),
        )

        # assert that the calibration has been found
        assert self.test_loader._stage_calibration
        mock_get_dataframe.assert_called_once()
        mock_calibrate.assert_called_once()


class TestSmartEMDiskDataLoader:
    @mock.patch("smartem.data_model.torch.pd.read_csv")
    def test_disk_data_loader(self, mock_read_csv, tmp_path):
        # grid square data which would be read from a csv file
        mock_read_csv.return_value = pd.DataFrame(
            data={
                "grid_square": [tmp_path / "grid0.tif"] * 10,
                "accummotiontotal": np.arange(10),
                "estimatedresolution": np.arange(10),
                "maxvalueprobdistribution": np.arange(10),
                "ctfmaxresolution": np.arange(10),
                "foil_hole_x": 0.1 * np.ones(10),
                "foil_hole_y": 0.2 * np.ones(10),
                "grid_square_x": 0.1 * np.ones(10),
                "grid_square_y": 0.2 * np.ones(10),
                "grid_square_pixel_size": 3 * np.ones(10),
            }
        )

        # make image file expected by loader
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )

        # run the loader
        self.test_loader = torch.SmartEMDiskDataLoader(
            level="grid_square",
            data_dir=tmp_path,
            full_res=True,
            labels_csv="labels.csv",
            num_samples=2,
            sub_sample_size=(1, 1),
            allowed_labels={"test": True},
            seed=0,
        )

        # assert that the csv would have been read and a calibration has been found
        assert self.test_loader._stage_calibration
        mock_read_csv.assert_called_once()


class TestSmartEMMaskDataLoader:
    @pytest.fixture(autouse=True)
    @mock.patch("smartem.data_model.torch.pd.read_csv")
    def setUp(self, mock_read_csv, tmp_path):
        # grid square data which would be read from a csv file
        mock_read_csv.return_value = pd.DataFrame(
            data={
                "grid_square": [tmp_path / "grid0.tif"] * 10,
                "accummotiontotal": np.arange(10),
                "estimatedresolution": np.arange(10),
                "maxvalueprobdistribution": np.arange(10),
                "ctfmaxresolution": np.arange(10),
                "foil_hole_x": 0.1 * np.ones(10),
                "foil_hole_y": 0.2 * np.ones(10),
                "grid_square_x": 0.1 * np.ones(10),
                "grid_square_y": 0.2 * np.ones(10),
                "grid_square_pixel_size": 3 * np.ones(10),
            }
        )

        # make image files expected by loader
        tifffile.imwrite(
            tmp_path / "grid0.tif",
            np.array([[110, 120], [130, 140]], dtype="uint8"),
            photometric="minisblack",
        )
        np.save(str(tmp_path) + "/grid0.npy", np.array([1, 2]))

        # run the loader
        self.test_loader = torch.SmartEMMaskDataLoader(
            data_dir=tmp_path, labels_csv="labels.csv"
        )

        # assert that the csv would have been read
        mock_read_csv.assert_called_once()

    def test_len(self):
        # assert the length can be returned using len
        assert len(self.test_loader) == 1

    def test_get_item(self):
        return_value = self.test_loader[0]

        # assert the grid tiff and numpy file results are stored
        assert return_value[0][0][0, 0] == 110
        assert return_value[0][0][0, 1] == 120
        assert return_value[0][0][1, 0] == 130
        assert return_value[0][0][1, 1] == 140
        assert return_value[1][0] == 1
        assert return_value[1][1] == 2
