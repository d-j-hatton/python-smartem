from unittest import mock

from smartem.cli import export


@mock.patch("smartem.cli.export.argparse.ArgumentParser")
@mock.patch("smartem.cli.export.DataAPI")
@mock.patch("smartem.cli.export.export_foil_holes")
def test_run(mock_export, mock_api, mock_argparse):
    export.run()

    # assert the arguments are read in
    mock_argparse.assert_called_once()
    assert mock_argparse().add_argument.call_count == 5
    mock_argparse().parse_args.assert_called_once()

    # assert the foil holes are exported
    mock_api.assert_called_once()
    mock_export.assert_called_once()
