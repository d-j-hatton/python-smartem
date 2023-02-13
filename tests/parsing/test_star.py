import pytest
from unittest import mock

import os

from smartem.parsing import star


@pytest.fixture
def make_sample_star(tmp_path):
    os.mkdir(tmp_path / "MotionCorr")
    os.mkdir(tmp_path / "MotionCorr/job001")
    with open(
            tmp_path / "MotionCorr/job001/corrected_micrographs.star",
            "w"
    ) as f:
        f.write(
            "data_micrographs\nloop_\n"
            "_rlnmicrographname\n_rlnaccummotiontotal\ntest  1"
        )


def test_open_star_file(make_sample_star, tmp_path):
    return_value = star.open_star_file(
        tmp_path / "MotionCorr/job001/corrected_micrographs.star"
    )

    assert return_value


def test_get_columns(make_sample_star, tmp_path):
    return_value = star.get_columns(
        star.open_star_file(
            tmp_path / "MotionCorr/job001/corrected_micrographs.star"
        )
    )

    assert return_value == ["_rlnmicrographname", "_rlnaccummotiontotal"]


def test_get_column_data(make_sample_star, tmp_path):
    return_value = star.get_column_data(
        star.open_star_file(
            tmp_path / "MotionCorr/job001/corrected_micrographs.star"
        ),
        columns=["_rlnmicrographname", "_rlnaccummotiontotal"],
        block_tag="micrographs"
    )

    assert return_value == {
        "_rlnmicrographname": ["test"],
        "_rlnaccummotiontotal": [1]
    }


@mock.patch("smartem.parsing.relion_default.DataAPI")
def test_insert_exposure_data(mock_api, tmp_path):
    # create mock exposure with a name that matches the tag data
    exposure_mock = mock.MagicMock()
    exposure_mock.exposure_name = "test.jpg"
    mock_api.get_exposures.return_value = [exposure_mock]

    star.insert_exposure_data(
        data={"_exposure_tag": ["test"], "_dummy_tag": [1]},
        exposure_tag="_exposure_tag",
        star_file_path=str(tmp_path),
        extractor=mock_api,
        validate=True,
        extra_suffix="",
        project="dummy"
    )

    mock_api.get_exposures.assert_called_once()
    mock_api.put.assert_called_once()
    assert mock_api.put.call_args[0] != ([],)


@mock.patch("smartem.parsing.relion_default.DataAPI")
def test_insert_particle_data(mock_api, tmp_path):
    # create mock exposure with a name that matches the tag data
    exposure_mock = mock.MagicMock()
    exposure_mock.exposure_name = "test.jpg"
    mock_api.get_exposures.return_value = [exposure_mock]

    # create mock particle which is returned from mock_api.put
    put_mock = mock.MagicMock()
    put_mock.particle_id = 1
    mock_api.put.return_value = [put_mock]

    star.insert_particle_data(
        data={
            "_exposure_tag": ["test"],
            "_dummy_tag": [1],
            "_x_tag": ["x"],
            "_y_tag": ["y"]
        },
        exposure_tag="_exposure_tag",
        x_tag="_x_tag",
        y_tag="_y_tag",
        star_file_path=str(tmp_path),
        extractor=mock_api,
        project="dummy"
    )

    mock_api.get_exposures.assert_called_once()
    mock_api.get_particles.assert_called_once()
    mock_api.put.assert_called()
    assert mock_api.put.call_count == 2


@mock.patch("smartem.parsing.relion_default.DataAPI")
def test_insert_particle_set(mock_api, tmp_path):
    # create mock exposure with a name that matches the tag data
    exposure_mock = mock.MagicMock()
    exposure_mock.exposure_name = "test.jpg"
    mock_api.get_exposures.return_value = [exposure_mock]

    # create mock particle which is returned from mock_api.put
    put_mock = mock.MagicMock()
    put_mock.particle_id = 1
    mock_api.put.return_value = [put_mock]

    # create mock particle set which is returned from mock_api.get_particle_sets
    set_mock = mock.MagicMock()
    set_mock.identifier = "set_tag"
    mock_api.get_particle_sets.return_value = [set_mock]

    star.insert_particle_set(
        data={
            "_exposure_tag": ["test"],
            "_set_id_tag": ["set_tag"],
            "_dummy_tag": [1],
            "_x_tag": ["x"],
            "_y_tag": ["y"]
        },
        set_name="test_set",
        set_id_tag="_set_id_tag",
        exposure_tag="_exposure_tag",
        x_tag="_x_tag",
        y_tag="_y_tag",
        star_file_path=str(tmp_path),
        extractor=mock_api,
        project="dummy",
        add_source_to_id=False
    )

    mock_api.get_particle_sets.assert_called_once()
    mock_api.get_exposures.assert_called_once()
    mock_api.get_particles.assert_called_once()
    mock_api.put.assert_called()
    assert mock_api.put.call_count == 3
