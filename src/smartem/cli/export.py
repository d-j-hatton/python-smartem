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
    parser.add_argument(
        "--use_adjusted_stage",
        action="store_true",
        dest="use_adjusted_stage",
    )
    parser.add_argument(
        "--no_masks",
        action="store_true",
    )
    parser.add_argument(
        "-e",
        "--extension",
        dest="extension",
        default="",
    )
    args = parser.parse_args()

    data_api = DataAPI()
    export_foil_holes(
        data_api,
        out_dir=Path(args.out_dir),
        projects=args.projects,
        use_adjusted_stage=args.use_adjusted_stage,
        foil_hole_masks=not args.no_masks,
        alternative_extension=args.extension,
    )
