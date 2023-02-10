import pytest
from unittest import mock

from smartem.cli import initialise


@mock.patch("smartem.cli.initialise.argparse.ArgumentParser")
@mock.patch("smartem.cli.initialise.subprocess")
@mock.patch("smartem.cli.initialise.setup")
def test_run(mock_setup, mock_subprocees, mock_argparse, tmp_path):
    mock_argparse().parse_args().data_dir = tmp_path
    mock_argparse().parse_args().port = 101
    mock_subprocees.run().returncode = 0

    initialise.run()

    mock_argparse.assert_called()
    assert mock_argparse.call_count == 3
    mock_argparse().add_argument.assert_called()
    assert mock_argparse().add_argument.call_count == 3
    mock_argparse().parse_args.assert_called()
    assert mock_argparse().parse_args.call_count == 3

    mock_subprocees.run.assert_called()
    assert mock_subprocees.run.call_count == 5

    mock_setup.assert_called_once()
