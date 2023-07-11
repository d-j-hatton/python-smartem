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
    parser.add_argument(
        "--grid-square",
        type=int,
        help="Grid square EPU ID",
        dest="grid_square",
        default=0,
    )
    parser.add_argument(
        "--switch-xy",
        help="Switch the x and y axes in display",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--flip-x",
        help="Flip x axis in display",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--flip-y",
        help="Flip y axis in display",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    if args.atlas_dir and args.sample is None:
        exit("If --atlas-dir is specified then --sample must also be specified")

    if args.atlas_dir:
        a = Atlas(Path(args.atlas_dir), args.sample, epu_data_dir=Path(args.epu_dir))
        a.display()
    else:
        gs = GridSquare(Path(args.epu_dir), args.grid_square)
        gs.display()
