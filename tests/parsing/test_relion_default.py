import os
from unittest import mock

import pytest

from smartem.parsing import relion_default


@pytest.fixture
def make_relion_folders(tmp_path):
    # make the folder structures which relion uses
    os.mkdir(tmp_path / "MotionCorr")
    os.mkdir(tmp_path / "MotionCorr/job001")
    with open(tmp_path / "MotionCorr/job001/corrected_micrographs.star", "w") as f:
        f.write(
            "data_micrographs\nloop_\n"
            "_rlnmicrographname\n_rlnaccummotiontotal\ntest  1"
        )

    os.mkdir(tmp_path / "CtfFind")
    os.mkdir(tmp_path / "CtfFind/job001")
    with open(tmp_path / "CtfFind/job001/micrographs_ctf.star", "w") as f:
        f.write(
            "data_micrographs\nloop_\n"
            "_rlnmicrographname\n_rlnctfmaxresolution\ntest  5"
        )

    os.mkdir(tmp_path / "Class2D")
    os.mkdir(tmp_path / "Class2D/job001")
    with open(tmp_path / "Class2D/job001/run_it020_data.star", "w") as f:
        f.write(
            "data_particles\nloop_\n"
            "_rlnmicrographname\n_rlncoordinatex\n_rlncoordinatey\n"
            "_rlnmaxvalueprobdistribution\n_rlnclassnumber\ntest  0  1  2  [3]"
        )
    with open(tmp_path / "Class2D/job001/run_it020_model.star", "w") as f:
        f.write(
            "data_model_classes\nloop_\n"
            "_rlnreferenceimage\n_rlnestimatedresolution\n0[3]@test 0"
        )


@mock.patch("smartem.parsing.relion_default.DataAPI")
@mock.patch("smartem.parsing.relion_default.insert_exposure_data")
@mock.patch("smartem.parsing.relion_default.insert_particle_data")
@mock.patch("smartem.parsing.relion_default.insert_particle_set")
def test_gather_relion_defaults(
    mock_set, mock_particle, mock_exposure, mock_api, make_relion_folders, tmp_path
):
    relion_default.gather_relion_defaults(
        relion_dir=tmp_path,
        data_handler=mock_api,
        project="test",
        class_2d_excludes=None,
    )

    assert mock_exposure.call_count == 2
    mock_particle.assert_called_once()
    mock_set.assert_called_once()
