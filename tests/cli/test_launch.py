from unittest import mock

from smartem.cli import launch


@mock.patch("smartem.cli.launch.DataAPI")
@mock.patch("smartem.cli.launch.App")
def test_run(mock_app, mock_api):
    launch.run()

    mock_api.assert_called_once()
    mock_app.assert_called_once()
    mock_app().start.assert_called_once()
