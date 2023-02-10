import pytest
from unittest import mock

from smartem.data_model import structure


def test_extract_keys_avg_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.__getitem__().key = "test_exposure"
    mock_sql_result.__getitem__().value = 0

    return_value = structure.extract_keys(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    assert return_value
    assert return_value["test_exposure"].size == 0
    assert return_value["test_key"].size == 0
    assert return_value["test_set_key"].size == 0
    mock_sql_result.__getitem__.assert_called_with(0)
    mock_sql_result.__getitem__().exposure_name.__hash__.assert_called()
    assert mock_sql_result.__getitem__().exposure_name.__hash__.call_count == 5


def test_extract_keys_use_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.__getitem__().key = "test_key"
    mock_sql_result.__getitem__().value = 0

    return_value = structure.extract_keys(
        sql_result=[mock_sql_result],
        exposure_keys=[],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    assert return_value
    assert return_value["test_key"].size == 0
    assert return_value["test_set_key"].size == 0
    mock_sql_result.__getitem__.assert_called_with(0)
    mock_sql_result.__getitem__().particle_id.__hash__.assert_called()
    assert mock_sql_result.__getitem__().particle_id.__hash__.call_count == 5


def test_extract_keys_use_exposure():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.__getitem__().key = "test_exposure"
    mock_sql_result.__getitem__().value = 0

    return_value = structure.extract_keys(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=[],
        particle_set_keys=[]
    )

    assert return_value
    assert return_value["test_exposure"].size == 1
    mock_sql_result.__getitem__.assert_called_with(0)
    mock_sql_result.__getitem__().exposure_name.__hash__.assert_called()
    assert mock_sql_result.__getitem__().exposure_name.__hash__.call_count == 4


def test_extract_keys_with_foil_hole_averages_avg_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_exposure"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_foil_hole_averages(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    assert type(return_value) == dict
    assert return_value["test_exposure"]
    assert return_value["test_key"]
    assert return_value["test_set_key"]
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 1
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 6
    mock_sql_result.foil_hole_name.__hash__.assert_called()
    assert mock_sql_result.foil_hole_name.__hash__.call_count == 6


def test_extract_keys_with_foil_hole_averages_use_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_key"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_foil_hole_averages(
        sql_result=[mock_sql_result],
        exposure_keys=[],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    assert type(return_value) == dict
    assert return_value["test_key"]
    assert return_value["test_set_key"]
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 6
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 1
    mock_sql_result.foil_hole_name.__hash__.assert_called()
    assert mock_sql_result.foil_hole_name.__hash__.call_count == 6


def test_extract_keys_with_foil_hole_averages_use_exposure():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_exposure"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_foil_hole_averages(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=[],
        particle_set_keys=[]
    )

    assert type(return_value) == dict
    assert return_value["test_exposure"]
    print(mock_sql_result.mock_calls)
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 1
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 5
    mock_sql_result.foil_hole_name.__hash__.assert_called()
    assert mock_sql_result.foil_hole_name.__hash__.call_count == 6


def test_extract_keys_with_grid_square_averages_avg_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_exposure"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_grid_square_averages(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    print(mock_sql_result.mock_calls)
    assert type(return_value) == dict
    assert return_value["test_exposure"]
    assert return_value["test_key"]
    assert return_value["test_set_key"]
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 1
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 6
    mock_sql_result.grid_square_name.__hash__.assert_called()
    assert mock_sql_result.grid_square_name.__hash__.call_count == 6


def test_extract_keys_with_grid_square_averages_use_particles():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_key"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_grid_square_averages(
        sql_result=[mock_sql_result],
        exposure_keys=[],
        particle_keys=["test_key"],
        particle_set_keys=["test_set_key"]
    )

    assert type(return_value) == dict
    assert return_value["test_key"]
    assert return_value["test_set_key"]
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 6
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 1
    mock_sql_result.grid_square_name.__hash__.assert_called()
    assert mock_sql_result.grid_square_name.__hash__.call_count == 6


def test_extract_keys_with_grid_square_averages_use_exposure():
    mock_sql_result = mock.MagicMock()
    mock_sql_result.key = "test_exposure"
    mock_sql_result.value = 0

    return_value = structure.extract_keys_with_grid_square_averages(
        sql_result=[mock_sql_result],
        exposure_keys=["test_exposure"],
        particle_keys=[],
        particle_set_keys=[]
    )

    assert type(return_value) == dict
    assert return_value["test_exposure"]
    print(mock_sql_result.mock_calls)
    mock_sql_result.particle_id.__hash__.assert_called()
    assert mock_sql_result.particle_id.__hash__.call_count == 1
    mock_sql_result.exposure_name.__hash__.assert_called()
    assert mock_sql_result.exposure_name.__hash__.call_count == 5
    mock_sql_result.grid_square_name.__hash__.assert_called()
    assert mock_sql_result.grid_square_name.__hash__.call_count == 6
