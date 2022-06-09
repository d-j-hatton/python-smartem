import argparse
from pathlib import Path

from smartem.data_model.extract import DataAPI
from smartem.parsing.export import export_foil_holes


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--out_dir",
        help="Directory to export to",
        dest="out_dir",
        default=".",
    )
    parser.add_argument(
        "-p",
        "--projects",
        nargs="+",
        help="Names of smartEM projects to export",
        dest="projects",
    )
    args = parser.parse_args()

    data_api = DataAPI()
    export_foil_holes(data_api, out_dir=Path(args.out_dir), projects=args.projects)
