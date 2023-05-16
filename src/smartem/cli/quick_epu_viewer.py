import argparse
from pathlib import Path

from smartem.parsing.epu_vis import Atlas


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
        required=True,
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Sample number within atlas directory",
        dest="sample",
        required=True,
    )
    args = parser.parse_args()

    a = Atlas(Path(args.atlas_dir), args.sample, epu_data_dir=Path(args.epu_dir))
    a.display()
