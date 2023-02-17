import os
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from smartem.parsing import epu

tile_file = Path("Images-Disc1/GridSquare_1/Tile_sample.xml")
microscope_grid_file = Path("Images-Disc1/GridSquare_1/GridSquare_date_time.xml")
foil_hole_file = Path("Images-Disc1/GridSquare_1/FoilHoles/FoilHole_1_date_time.xml")
exposure_file = Path("Images-Disc1/GridSquare_1/Data/FoilHole_2_Data_1_1_date_time.xml")
grid_square_file = Path("Metadata/GridSquare_1.dm")
grid_metadata_file = Path("Metadata/Atlas.dm")


@pytest.fixture
def make_test_folder_structure(tmp_path):
    os.mkdir(tmp_path / "Metadata")
    os.mkdir(tmp_path / "Images-Disc1")
    os.mkdir(tmp_path / "Images-Disc1/GridSquare_1")
    os.mkdir(tmp_path / "Images-Disc1/GridSquare_1/FoilHoles")
    os.mkdir(tmp_path / "Images-Disc1/GridSquare_1/Data")


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
    data_to_write.write(tmp_path / foil_hole_file)
    data_to_write.write(tmp_path / exposure_file)


@pytest.fixture
def write_sample_metadata_xml(make_test_folder_structure, tmp_path):
    """
    Write an example xml file with the same structure
    as the metadata outputs for the foil holes
    """
    grid_square = ET.Element("GridSquareXml")
    target_locations = ET.SubElement(grid_square, "TargetLocations")
    target_locations_eff = ET.SubElement(target_locations, "TargetLocationsEfficient")
    serialization_array = ET.SubElement(target_locations_eff, "a:m_serializationArray")
    for block in range(3):
        key_value_pair = ET.SubElement(
            serialization_array, "b:KeyValuePairOfintTargetLocationTest"
        )
        b_key = ET.SubElement(key_value_pair, "b:key")
        b_key.text = str(block + 1)

        b_value = ET.SubElement(key_value_pair, "b:value")
        grid_bar = ET.SubElement(b_value, "IsNearGridBar")
        grid_bar.text = ["false", "true", "false"][block]
        position_corrected = ET.SubElement(b_value, "IsPositionCorrected")
        position_corrected.text = ["true", "false", "true"][block]

        pixel_center = ET.SubElement(b_value, "PixelCenter")
        pixel_center_x = ET.SubElement(pixel_center, "c:x")
        pixel_center_x.text = ["100.9", "201.9", "302.9"][block]
        pixel_center_y = ET.SubElement(pixel_center, "c:y")
        pixel_center_y.text = ["201.9", "302.9", "100.9"][block]
        pixel_width_height = ET.SubElement(b_value, "PixelWidthHeight")
        pixel_height = ET.SubElement(pixel_width_height, "c:height")
        pixel_height.text = ["2.0", "3.0", "0.0"][block]

        stage_pos = ET.SubElement(b_value, "StagePosition")
        stage_pos_x = ET.SubElement(stage_pos, "c:X")
        stage_pos_x.text = ["100.9", "201.9", "302.9"][block]
        stage_pos_y = ET.SubElement(stage_pos, "c:Y")
        stage_pos_y.text = ["201.9", "302.9", "100.9"][block]

        correct_stage_pos = ET.SubElement(b_value, "CorrectedStagePosition")
        correct_stage_pos_x = ET.SubElement(correct_stage_pos, "c:X")
        correct_stage_pos_x.text = ["100.6", "201.6", "302.6"][block]
        correct_stage_pos_y = ET.SubElement(correct_stage_pos, "c:Y")
        correct_stage_pos_y.text = ["201.6", "302.6", "100.6"][block]

    data_to_write = ET.ElementTree(grid_square)
    data_to_write.write(tmp_path / grid_square_file)


@pytest.fixture
def write_sample_atlas_xml(make_test_folder_structure, tmp_path):
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
            key_value_node = ET.SubElement(key_value_pairs, "KeyValuePairOfintNodeXml")
            atlas_key = ET.SubElement(key_value_node, "key")
            atlas_key.text = str(block + 1) + str(subblock + 1)
            atlas_value = ET.SubElement(key_value_node, "value")
            atlas_pos = ET.SubElement(atlas_value, "b:PositionOnTheAtlas")

            physical_pos = ET.SubElement(atlas_pos, "c:Physical")
            physical_x = ET.SubElement(physical_pos, "d:x")
            physical_x.text = ["1.9", "2.9"][block]
            physical_y = ET.SubElement(physical_pos, "d:y")
            physical_y.text = ["2.9", "1.9"][subblock]

            center_pos = ET.SubElement(atlas_pos, "c:Center")
            center_x = ET.SubElement(center_pos, "d:x")
            center_x.text = ["1.9", "2.9"][block]
            center_y = ET.SubElement(center_pos, "d:y")
            center_y.text = ["2.9", "1.9"][subblock]

    data_to_write = ET.ElementTree(atlas_session)
    data_to_write.write(tmp_path / grid_metadata_file)


def test_parse_epu_xml(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_xml(tmp_path / microscope_grid_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["stage_position", "pixel_size", "readout_area"]
    assert return_value["stage_position"] == (1.5 * 1e9, 2.5 * 1e9)
    assert return_value["pixel_size"] == 1.5 * 1e9
    assert return_value["readout_area"] == (1, 2)


def test_parse_epu_xml_version(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_xml_version(tmp_path / microscope_grid_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["software", "version"]
    assert return_value["software"] == "ApplicationSoftware"
    assert return_value["version"] == "ApplicationSoftwareVersion"


def test_metadata_foil_hole_positions(write_sample_metadata_xml, tmp_path):
    return_value = epu.metadata_foil_hole_positions(tmp_path / grid_square_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["1", "2", "3"]
    assert return_value["1"] == (100, 201)
    assert return_value["2"] == (201, 302)
    assert return_value["3"] == (302, 100)


def test_metadata_grid_square_positions(write_sample_atlas_xml, tmp_path):
    return_value = epu.metadata_grid_square_positions(tmp_path / grid_metadata_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["11", "12", "21", "22"]
    assert return_value["11"] == (1, 2)
    assert return_value["12"] == (1, 1)
    assert return_value["21"] == (2, 2)
    assert return_value["22"] == (2, 1)


def test_metadata_grid_square_stage(write_sample_atlas_xml, tmp_path):
    return_value = epu.metadata_grid_square_stage(tmp_path / grid_metadata_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["11", "12", "21", "22"]
    assert return_value["11"] == (1.9 * 1e9, 2.9 * 1e9)
    assert return_value["12"] == (1.9 * 1e9, 1.9 * 1e9)
    assert return_value["21"] == (2.9 * 1e9, 2.9 * 1e9)
    assert return_value["22"] == (2.9 * 1e9, 1.9 * 1e9)


def test_mask_foil_hope_positions(write_sample_metadata_xml, tmp_path):
    return_value = epu.mask_foil_hole_positions(
        tmp_path / grid_square_file, (320, 350), None
    )

    # expect an array of False except around the foil hole positions
    expected_return = np.zeros((320, 350), dtype=bool)

    expected_return[100, 201] = True
    expected_return[99, 201] = True
    expected_return[101, 201] = True
    expected_return[100, 200] = True
    expected_return[100, 202] = True

    expected_return[302, 100] = True
    expected_return[301, 100] = True
    expected_return[303, 100] = True
    expected_return[302, 99] = True
    expected_return[302, 101] = True

    expected_return = np.transpose(expected_return)

    assert (return_value == expected_return).all()


def test_metadata_foil_hole_stage(write_sample_metadata_xml, tmp_path):
    return_value = epu.metadata_foil_hole_stage(tmp_path / grid_square_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["1", "2", "3"]
    assert return_value["1"] == (100.9 * 1e9, 201.9 * 1e9)
    assert return_value["2"] == (201.9 * 1e9, 302.9 * 1e9)
    assert return_value["3"] == (302.9 * 1e9, 100.9 * 1e9)


def test_metadata_foil_hole_corrected_stage(write_sample_metadata_xml, tmp_path):
    return_value = epu.metadata_foil_hole_corrected_stage(tmp_path / grid_square_file)

    assert type(return_value) == dict
    assert list(return_value.keys()) == ["1", "2", "3"]
    assert return_value["1"] == (100.6 * 1e9, 201.6 * 1e9)
    assert return_value["2"] == (None, None)
    assert return_value["3"] == (302.6 * 1e9, 100.6 * 1e9)


def test_calibrate_coordinate_system(write_sample_metadata_xml, tmp_path):
    return_value = epu.calibrate_coordinate_system(tmp_path / grid_square_file)

    assert not return_value.inverted
    assert return_value.x_flip
    assert return_value.y_flip


def test_create_atlas_and_tiles(write_sample_microscope_xml, tmp_path):
    mock_extractor = mock.MagicMock()

    tile_jpg_file = open(tmp_path / tile_file.with_suffix(".jpg"), "w")
    tile_jpg_file.close()

    epu.create_atlas_and_tiles(tmp_path / microscope_grid_file, mock_extractor)

    assert mock_extractor.put.call_count == 2
    assert mock.call([]) not in mock_extractor.put.call_args_list


def test_parse_epu_version(write_sample_microscope_xml, tmp_path):
    return_value = epu.parse_epu_version(tmp_path / "Images-Disc1")

    assert return_value == ("ApplicationSoftware", "ApplicationSoftwareVersion")


def test_parse_epu_dir(
    write_sample_microscope_xml, write_sample_metadata_xml, tmp_path
):
    grid_jpg_file = open(tmp_path / microscope_grid_file.with_suffix(".jpg"), "w")
    grid_jpg_file.close()

    foil_hole_jpg_file = open(tmp_path / foil_hole_file.with_suffix(".jpg"), "w")
    foil_hole_jpg_file.close()

    exposure_jpg_file = open(tmp_path / exposure_file.with_suffix(".jpg"), "w")
    exposure_jpg_file.close()

    mock_extractor = mock.MagicMock()

    epu.parse_epu_dir(tmp_path / "Images-Disc1", tmp_path, mock_extractor, "test")

    assert mock_extractor.put.call_count == 4
    assert mock.call([]) not in mock_extractor.put.call_args_list
