import argparse
from pathlib import Path

from smartem.parsing.epu_vis import Atlas, GridSquare


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--epu-dir",
        help="Path to EPU directory",
        dest="epu_dir",
        default=None,
    )
    parser.add_argument(
        "--atlas-dir",
        help="Path to EPU Atlas directory",
        dest="atlas_dir",
        default=None,
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Sample number within atlas directory",
        dest="sample",
        default=None,
    )
    args = parser.parse_args()

    if args.atlas_dir and args.sample is None:
        exit("If --atlas-dir is specified then --sample must also be specified")

    if args.atlas_dir:
        a = Atlas(Path(args.atlas_dir), args.sample, epu_data_dir=Path(args.epu_dir))
        a.display()
    else:
        gs = GridSquare(Path(args.epu_dir), 0)
        gs.display()
