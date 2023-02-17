import copy
import os
from unittest import mock

from smartem.parsing import export


def test_get_dataframe():
    mock_api = mock.MagicMock()
    mock_data = mock.MagicMock()

    # set up data structure to be read
    mock_data.thumbnail = "sample.jpg"
    mock_api.get_grid_squares.return_value = [mock_data]

    mock_data.foil_hole_name = "hole_1"
    mock_api.get_foil_holes.return_value = [mock_data]

    mock_data.acquisition_directory = "."
    mock_data.pixel_size = 1
    mock_data.stage_position_x = 2
    mock_data.stage_position_y = 3
    mock_api.get_project.return_value = mock_data

    mock_data.atlas_id = 1
    mock_api.get_atlas_from_project.return_value = mock_data

    # set up mocks each with a different key value that get_dataframe reads
    mock_data.value = 1
    mock_data_rlnaccummotiontotal = copy.copy(mock_data)
    mock_data_rlnaccummotiontotal.key = "_rlnaccummotiontotal"
    mock_data_rlnctfmaxresolution = copy.copy(mock_data)
    mock_data_rlnctfmaxresolution.key = "_rlnctfmaxresolution"
    mock_data_rlnmaxvalueprobdistribution = copy.copy(mock_data)
    mock_data_rlnmaxvalueprobdistribution.key = "_rlnmaxvalueprobdistribution"
    mock_data_rlnestimatedresolution = copy.copy(mock_data)
    mock_data_rlnestimatedresolution.key = "_rlnestimatedresolution"
    mock_api.get_atlas_info.return_value = [
        mock_data_rlnaccummotiontotal,
        mock_data_rlnctfmaxresolution,
        mock_data_rlnmaxvalueprobdistribution,
        mock_data_rlnestimatedresolution,
    ]

    return_value = export.get_dataframe(
        data_api=mock_api,
        projects=["dummy"],
        grid_squares=None,
        out_gs_paths=None,
        out_fh_paths=None,
        data_labels=None,
        use_adjusted_stage=False,
    )

    # assert that the dataframe has been returned with the correct keys and values
    assert return_value["grid_square"][0] == "sample.jpg"
    assert return_value["grid_square_pixel_size"][0] == 1
    assert return_value["grid_square_x"][0] == 2
    assert return_value["grid_square_y"][0] == 3
    assert return_value["foil_hole"][0] == "sample.jpg"
    assert return_value["foil_hole_pixel_size"][0] == 1
    assert return_value["foil_hole_x"][0] == 2
    assert return_value["foil_hole_y"][0] == 3
    assert return_value["accummotiontotal"][0] == 1.0
    assert return_value["ctfmaxresolution"][0] == 1.0
    assert return_value["estimatedresolution"][0] == 1.0
    assert return_value["maxvalueprobdistribution"][0] == 1.0

    mock_api.get_grid_squares.assert_called_once()
    mock_api.get_foil_holes.assert_called_once()
    mock_api.get_project.assert_called_once()
    mock_api.get_atlas_from_project.assert_called_once()
    mock_api.get_atlas_info.assert_called_once()


@mock.patch("smartem.parsing.export.mask_foil_hole_positions")
@mock.patch("smartem.parsing.export.calibrate_coordinate_system")
@mock.patch("smartem.parsing.export.yaml")
def test_export_foil_holes(mock_yaml, mock_calibrate, mock_mask, tmp_path):
    # create files expected by smartem
    os.mkdir(tmp_path / "test_export_foil_holes0")
    with open(tmp_path / "test_export_foil_holes0/sample.jpg", "w") as f:
        f.write("data")
    with open(tmp_path / "test_export_foil_holes0/sample.mrc", "w") as f:
        f.write("data")
    try:
        os.mkdir(tmp_path / "../Metadata")
    except FileExistsError:
        pass
    with open(tmp_path / "../Metadata/grid_1.dm", "w") as f:
        f.write("<data></data>")

    mock_api = mock.MagicMock()
    mock_data = mock.MagicMock()

    # set up data structure to be read
    mock_data.thumbnail = tmp_path / "test_export_foil_holes0/sample.jpg"

    mock_api.get_grid_squares.return_value = [mock_data]

    mock_data.foil_hole_name = "hole_1"
    mock_api.get_foil_holes.return_value = [mock_data]

    mock_data.acquisition_directory = tmp_path
    mock_data.grid_square_name = "grid_1"
    mock_api.get_project.return_value = mock_data

    mock_data.atlas_id = 1
    mock_api.get_atlas_from_project.return_value = mock_data

    # set up mocks with the key values that get_dataframe reads
    mock_data.value = 1
    mock_data_rlnaccummotiontotal = copy.copy(mock_data)
    mock_data_rlnaccummotiontotal.key = "_rlnaccummotiontotal"
    mock_data_rlnctfmaxresolution = copy.copy(mock_data)
    mock_data_rlnctfmaxresolution.key = "_rlnctfmaxresolution"
    mock_data_rlnmaxvalueprobdistribution = copy.copy(mock_data)
    mock_data_rlnmaxvalueprobdistribution.key = "_rlnmaxvalueprobdistribution"
    mock_data_rlnestimatedresolution = copy.copy(mock_data)
    mock_data_rlnestimatedresolution.key = "_rlnestimatedresolution"
    mock_api.get_atlas_info.return_value = [
        mock_data_rlnaccummotiontotal,
        mock_data_rlnctfmaxresolution,
        mock_data_rlnmaxvalueprobdistribution,
        mock_data_rlnestimatedresolution,
    ]

    export.export_foil_holes(
        data_api=mock_api,
        out_dir=tmp_path,
        projects=["dummy"],
        use_adjusted_stage=False,
        foil_hole_masks=True,
        alternative_extension="",
    )

    mock_api.get_grid_squares.assert_called_once()
    mock_api.get_foil_holes.assert_called_once()
    assert mock_api.get_project.call_count == 2
    mock_api.get_atlas_from_project.assert_called_once()
    mock_api.get_atlas_info.assert_called_once()

    mock_mask.assert_called_once()
    mock_calibrate.assert_called_once()
    mock_yaml.dump.assert_called_once()
