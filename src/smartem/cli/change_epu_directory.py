import argparse

from smartem.data_model.extract import DataAPI


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--project_name",
        help="Name of project to change EPU directory of",
        dest="project_name",
    )
    parser.add_argument(
        "--new_epu_dir",
        help="Path to new EPU directory",
        dest="epu_dir",
    )
    parser.add_argument(
        "--new_atlas_image",
        help="Path to new Atlas image",
        dest="atlas_image",
    )
    args = parser.parse_args()

    extractor = DataAPI()
    extractor.update_project(args.project_name, acquisition_directory=args.epu_dir)
    project = extractor.get_project(project_name=args.project_name)
    extractor.update_atlas(project.atlas_id, thumbnail=args.atlas_image)
