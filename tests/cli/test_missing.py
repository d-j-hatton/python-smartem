from unittest import mock

from smartem.cli import missing


@mock.patch("smartem.cli.missing.argparse.ArgumentParser")
@mock.patch("smartem.cli.missing.DataAPI")
@mock.patch("smartem.cli.missing.open_star_file")
@mock.patch("smartem.cli.missing.get_column_data")
def test_run(mock_get_column, mock_star, mock_api, mock_argparse, tmp_path):
    mock_get_column.return_value = {
        "_rlnmicrographmoviename": ["test/test_file"]
    }

    mock_file_structure = mock.MagicMock()
    mock_file_structure.output = tmp_path / "tmp"
    mock_file_structure.project = "project"
    mock_argparse().parse_args.return_value = mock_file_structure

    missing.run()

    mock_argparse.assert_called()
    assert mock_argparse.call_count == 2
    mock_argparse().add_argument.assert_called()
    assert mock_argparse().add_argument.call_count == 3
    mock_argparse().parse_args.assert_called_once()

    mock_star.assert_called_once()
    mock_get_column.assert_called_once()

    mock_api.assert_called_once()
    mock_api().set_project.assert_called_once()
    mock_api().get_exposures.assert_called_once()
    mock_api().get_grid_squares.assert_called_once()
    mock_api().get_foil_holes.assert_called_once()
