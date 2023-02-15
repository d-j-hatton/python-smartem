from unittest import mock

from smartem.cli import initialise


@mock.patch("smartem.cli.initialise.argparse.ArgumentParser")
@mock.patch("smartem.cli.initialise.subprocess")
@mock.patch("smartem.cli.initialise.setup")
def test_run(mock_setup, mock_subprocess, mock_argparse, tmp_path):
    mock_argparse().parse_args().data_dir = tmp_path
    mock_argparse().parse_args().port = 101
    mock_subprocess.run().returncode = 0

    initialise.run()

    # assert the arguments are read in
    assert mock_argparse.call_count == 3
    assert mock_argparse().add_argument.call_count == 3
    assert mock_argparse().parse_args.call_count == 3

    # assert the environment is set up and run
    assert mock_subprocess.run.call_count == 5
    mock_setup.assert_called_once()
