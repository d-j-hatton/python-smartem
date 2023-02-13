from unittest import mock

from smartem.cli import change_epu_directory


@mock.patch("smartem.cli.change_epu_directory.argparse.ArgumentParser")
@mock.patch("smartem.cli.change_epu_directory.DataAPI")
def test_run(mock_api, mock_argparse):
    change_epu_directory.run()

    mock_argparse.assert_called_once()
    mock_argparse().add_argument.assert_called()
    assert mock_argparse().add_argument.call_count == 3
    mock_argparse().parse_args.assert_called_once()

    mock_api.assert_called_once()
    mock_api().update_project.assert_called_once()
    mock_api().get_project.assert_called_once()
    mock_api().update_project.assert_called_once()
