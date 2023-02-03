import pytest
from unittest.mock import MagicMock

import os
import xml.etree.ElementTree as ET

from smartem.parsing import epu

microscope_grid_file = "Data/GridSquare0/FoilHoles/FoilHole0.xml"
exposure_file = "Data/GridSquare0/"
foil_hole_file = "Metadata/GridSquare0.dm"
grid_metadata_file = "Metadata/sample_metadata.dm"
tile_file = "Data/GridSquare0/Tile_sample.xml"


@pytest.fixture
def make_test_folder_structure(tmp_path):
    os.mkdir(tmp_path / "Metadata")
    os.mkdir(tmp_path / "Data")
    os.mkdir(tmp_path / "Data/GridSquare0")
    os.mkdir(tmp_path / "Data/GridSquare0/FoilHoles")


@pytest.fixture
def write_sample_microscope_xml(make_test_folder_structure, tmp_path):
    """
    Write an example xml file with the same structure
    as the microscope outputs
    """

    microscope_image = ET.Element("MicroscopeImage")
    microscope_data = ET.SubElement(microscope_image, "microscopeData")

    stage = ET.SubElement(microscope_data, "stage")
    stage_position = ET.SubElement(stage, "Position")
    stage_position_x = ET.SubElement(stage_position, "X")
    stage_position_y = ET.SubElement(stage_position, "Y")
    stage_position_x.text = "1.5"
    stage_position_y.text = "2.5"

    acquisition = ET.SubElement(microscope_data, "acquisition")
    camera = ET.SubElement(acquisition, "camera")
    readout_area = ET.SubElement(camera, "ReadoutArea")
    readout_area_width = ET.SubElement(readout_area, "a:width")
    readout_area_height = ET.SubElement(readout_area, "a:height")
    readout_area_width.text = "1"
    readout_area_height.text = "2"

    core = ET.SubElement(microscope_data, "core")
    app_soft = ET.SubElement(core, "ApplicationSoftware")
    app_soft_ver = ET.SubElement(core, "ApplicationSoftwareVersion")
    app_soft.text = "ApplicationSoftware"
    app_soft_ver.text = "ApplicationSoftwareVersion"

    spatial_scale = ET.SubElement(microscope_image, "SpatialScale")
    pixel_size = ET.SubElement(spatial_scale, "pixelSize")
    pixel_size_x = ET.SubElement(pixel_size, "x")
    pixel_x_value = ET.SubElement(pixel_size_x, "numericValue")
    pixel_x_value.text = "1.5"

    data_to_write = ET.ElementTree(microscope_image)
    data_to_write.write(tmp_path / tile_file)
    data_to_write.write(tmp_path / microscope_grid_file)


@pytest.fixture
def write_sample_metadata_foil_hole_xml(make_test_folder_structure, tmp_path):
    """
    Write an example xml file with the same structure
    as the metadata outputs for the foil holes
    """

    grid_square = ET.Element("GridSquareXml")
    target_locations = ET.SubElement(grid_square, "TargetLocations")
    target_locations_eff = ET.SubElement(
        target_locations, "TargetLocationsEfficient"
    )
    serialization_array = ET.SubElement(
        target_locations_eff, "a:m_serializationArray"
    )
    for block in range(2):
        key_value_pair = ET.SubElement(
            serialization_array, "b:KeyValuePairOfintTargetLocationTest"
        )
        b_key = ET.SubElement(key_value_pair, "b:key")
        b_key.text = "test_key_" + str(block)

        b_value = ET.SubElement(key_value_pair, "b:value")
        grid_bar = ET.SubElement(b_value, "IsNearGridBar")
        grid_bar.text = ["false", "true"][block]
        position_corrected = ET.SubElement(b_value, "IsPositionCorrected")
        position_corrected.text = ["true", "false"][block]

        pixel_center = ET.SubElement(b_value, "PixelCenter")
        pixel_center_x = ET.SubElement(pixel_center, "c:x")
        pixel_center_x.text = ["1.9", "2.9"][block]
        pixel_center_y = ET.SubElement(pixel_center, "c:y")
        pixel_center_y.text = ["2.9", "1.9"][block]
        pixel_width_height = ET.SubElement(b_value, "PixelWidthHeight")
        pixel_height = ET.SubElement(pixel_width_height, "c:height")
        pixel_height.text = ["2.0", "1.0"][block]

        stage_pos = ET.SubElement(b_value, "StagePosition")
        stage_pos_x = ET.SubElement(stage_pos, "c:X")
        stage_pos_x.text = ["1.9", "2.9"][block]
        stage_pos_y = ET.SubElement(stage_pos, "c:Y")
        stage_pos_y.text = ["2.9", "1.9"][block]

        correct_stage_pos = ET.SubElement(b_value, "CorrectedStagePosition")
        correct_stage_pos_x = ET.SubElement(correct_stage_pos, "c:X")
        correct_stage_pos_x.text = ["1.6", "2.6"][block]
        correct_stage_pos_y = ET.SubElement(correct_stage_pos, "c:Y")
        correct_stage_pos_y.text = ["2.6", "1.6"][block]

    data_to_write = ET.ElementTree(grid_square)
    data_to_write.write(
        tmp_path / foil_hole_file,
    )


@pytest.fixture
def write_sample_metadata_grid_square_xml(make_test_folder_structure, tmp_path):
    """
        Write an example xml file with the same structure
        as the metadata outputs for the grid squares
        """

    atlas_session = ET.Element("AtlasSessionXml")
    atlas = ET.SubElement(atlas_session, "Atlas")
    tiles_efficient = ET.SubElement(atlas, "TilesEfficient")
    tiles_items = ET.SubElement(tiles_efficient, "_items")
    for block in range(2):
        tile_xml = ET.SubElement(tiles_items, "TileXml")
        tile_nodes = ET.SubElement(tile_xml, "Nodes")
        key_value_pairs = ET.SubElement(tile_nodes, "KeyValuePairs")

        for subblock in range(2):
            key_value_node = ET.SubElement(
                key_value_pairs, "KeyValuePairOfintNodeXml"
            )
            atlas_key = ET.SubElement(key_value_node, "key")
            atlas_key.text = "test_key_" + str(block) + str(subblock)
            atlas_value = ET.SubElement(key_value_node, "value")
            atlas_pos = ET.SubElement(atlas_value, "b:PositionOnTheAtlas")
            physical_pos = ET.SubElement(atlas_pos, "c:Physical")
            physical_x = ET.SubElement(physical_pos, "d:x")
            physical_y = ET.SubElement(physical_pos, "d:y")
            physical_x.text = ["1.9", "2.9"][block]
            physical_y.text = ["2.9", "1.9"][subblock]

    data_to_write = ET.ElementTree(atlas_session)
    data_to_write.write(tmp_path / grid_metadata_file)


def test_parse_epu_xml(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_xml(tmp_path / microscope_grid_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == [
        "stage_position",
        "pixel_size",
        "readout_area"
    ]
    assert return_value["stage_position"] == (1.5 * 1e9, 2.5 * 1e9)
    assert return_value["pixel_size"] == 1.5 * 1e9
    assert return_value["readout_area"] == (1, 2)


def test_parse_epu_xml_version(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_xml_version(tmp_path / microscope_grid_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["software", "version"]
    assert return_value["software"] == "ApplicationSoftware"
    assert return_value["version"] == "ApplicationSoftwareVersion"


def test_metadata_foil_hole_positions(
        write_sample_metadata_foil_hole_xml,
        tmp_path
):
    return_value = epu.metadata_foil_hole_positions(tmp_path / foil_hole_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["test_key_0", "test_key_1"]
    assert return_value["test_key_0"] == (1, 2)
    assert return_value["test_key_1"] == (2, 1)


def test_metadata_grid_square_stage(
        write_sample_metadata_grid_square_xml,
        tmp_path
):
    return_value = epu.metadata_grid_square_stage(tmp_path / grid_metadata_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == [
        "test_key_00",
        "test_key_01",
        "test_key_10",
        "test_key_11"
    ]
    assert return_value["test_key_00"] == (1.9 * 1e9, 2.9 * 1e9)
    assert return_value["test_key_01"] == (1.9 * 1e9, 1.9 * 1e9)
    assert return_value["test_key_10"] == (2.9 * 1e9, 2.9 * 1e9)
    assert return_value["test_key_11"] == (2.9 * 1e9, 1.9 * 1e9)


def test_mask_foil_hope_positions(
        write_sample_metadata_foil_hole_xml,
        tmp_path
):
    return_value = epu.mask_foil_hole_positions(
        tmp_path / foil_hole_file,
        (3, 4),
        None
    )

    assert (return_value == [
        [False, False, False],
        [False, True, False],
        [True, True, True],
        [False, True, False]
    ]).all()


def test_metadata_foil_hole_stage(
        write_sample_metadata_foil_hole_xml,
        tmp_path
):
    return_value = epu.metadata_foil_hole_stage(tmp_path / foil_hole_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["test_key_0", "test_key_1"]
    assert return_value["test_key_0"] == (1.9 * 1e9, 2.9 * 1e9)
    assert return_value["test_key_1"] == (2.9 * 1e9, 1.9 * 1e9)


def test_metadata_foil_hole_corrected_stage(
        write_sample_metadata_foil_hole_xml,
        tmp_path
):
    return_value = epu.metadata_foil_hole_corrected_stage(
        tmp_path / foil_hole_file
    )

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["test_key_0", "test_key_1"]
    assert return_value["test_key_0"] == (1.6 * 1e9, 2.6 * 1e9)
    assert return_value["test_key_1"] == (None, None)


'''
def test_calibrate_coordinate_system(
        write_sample_metadata_foil_hole_xml,
        tmp_path
):
    return_value = epu.calibrate_coordinate_system(
        tmp_path / "sample_metadata_foil_hole.xml"
    )

    assert return_value
'''


def test_create_atlas_and_tiles(write_sample_microscope_xml, tmp_path):
    mock_extractor = MagicMock()

    tile_jpg_file = open(tmp_path / (tile_file[:-4] + ".jpg"), 'w')
    tile_jpg_file.close()

    epu.create_atlas_and_tiles(tmp_path / microscope_grid_file, mock_extractor)

    mock_extractor.put.assert_called()
    try:
        mock_extractor.put.assert_called_with([])
        raise TypeError("extractor called with [], expected non-empty list")
    except AssertionError:
        pass


def test_parse_epu_version(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_version(tmp_path / "Data")

    assert return_value == (
        "ApplicationSoftware",
        "ApplicationSoftwareVersion"
    )


def test_parse_epu_dir(
        write_sample_microscope_xml,
        write_sample_metadata_foil_hole_xml,
        tmp_path):
    grid_jpg_file = open(tmp_path / (microscope_grid_file[:-4] + ".jpg"), 'w')
    grid_jpg_file.close()

    mock_extractor = MagicMock()

    epu.parse_epu_dir(tmp_path / "Data", tmp_path, mock_extractor, "test")

    mock_extractor.put.assert_called()
