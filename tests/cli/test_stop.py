from unittest import mock

from smartem.cli import stop


@mock.patch("smartem.cli.stop.argparse.ArgumentParser")
@mock.patch("smartem.cli.stop.os.getenv")
@mock.patch("smartem.cli.stop.yaml")
@mock.patch("smartem.cli.stop.subprocess")
def test_run(mock_subprocess, mock_yaml, mock_getenv, mock_argparse):
    mock_yaml.safe_load.return_value = {"password": "test"}
    mock_subprocess.run().returncode = 0

    stop.run()

    # assert the arguments are read in
    mock_argparse.assert_called_once()
    mock_argparse().add_argument.assert_called_once()
    mock_argparse().parse_args.assert_called_once()

    # assert the environment is loaded and run
    mock_getenv.assert_called_once()
    mock_yaml.safe_load.assert_called_once()
    assert mock_subprocess.run.call_count == 2
