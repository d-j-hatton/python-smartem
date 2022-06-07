import argparse
from pathlib import Path

from smartem.data_model.extract import DataAPI
from smartem.parsing.star import get_column_data, open_star_file


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--project",
        help="Project name",
        dest="project",
    )
    parser.add_argument(
        "-i",
        "--imported",
        help="Star file from Relion import job",
        dest="imported",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="File to dump results to",
        dest="output",
        default="./missing_movies",
    )
    args = parser.parse_args()

    star_file = open_star_file(Path(args.imported))
    movies = get_column_data(star_file, ["_rlnmicrographmoviename"], "movies")

    data_api = DataAPI()
    data_api.set_project(args.project)

    exposures = data_api.get_exposures()

    print(
        f"{len(exposures)} movies found in EPU directory, {len(movies['_rlnmicrographmoviename'])} movies imported in Relion (percentage {100*len(exposures)/len(movies['_rlnmicrographmoviename'])})"
    )

    foil_holes = data_api.get_foil_holes()
    imported_foil_holes = {
        f"FoilHole_{Path(m).name.split('_')[1]}": m.split("/")[1]
        for m in movies["_rlnmicrographmoviename"]
    }

    print(
        f"{len(foil_holes)} foil holes found in EPU directory, {len(imported_foil_holes)} foil holes imported in Relion (percentage {100*len(foil_holes)/len(imported_foil_holes)})"
    )

    grid_squares = data_api.get_grid_squares()
    imported_grid_squares = {m.split("/")[1] for m in movies["_rlnmicrographmoviename"]}

    print(
        f"{len(grid_squares)} grid squares found in EPU directory, {len(imported_grid_squares)} grid squares imported in Relion (percentage {100*len(grid_squares)/len(imported_grid_squares)})"
    )

    diff = set(imported_foil_holes.keys()) - {fh.foil_hole_name for fh in foil_holes}
    with open(f"{args.output}_{args.project}.txt", "w") as ofile:
        for d in diff:
            ofile.write(f"{imported_foil_holes[d]}/FoilHoles/{d}*\n")
