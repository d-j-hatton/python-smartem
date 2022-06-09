import shutil
from pathlib import Path
from typing import Dict, List, Optional

from pandas import DataFrame

from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import extract_keys_with_foil_hole_averages


def export_foil_holes(
    data_api: DataAPI, out_dir: Path = Path("."), projects: Optional[List[str]] = None
):
    if not projects:
        projects = [data_api._project]
    out_gs_paths = {}
    data: Dict[str, list] = {
        "grid_square": [],
        "foil_hole": [],
        "accummotiontotal": [],
        "ctfmaxresolution": [],
        "estimatedresolution": [],
    }

    for project in projects:
        data_api.set_project(project)
        grid_squares = data_api.get_grid_squares()
        foil_holes = data_api.get_foil_holes()

        data_labels = [
            "_rlnaccummotiontotal",
            "_rlnctfmaxresolution",
            "_rlnestimatedresolution",
        ]

        _project = data_api.get_project()
        atlas_id = data_api.get_atlas_from_project(_project).atlas_id
        atlas_info = data_api.get_atlas_info(
            atlas_id,
            ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
            [],
            ["_rlnestimatedresolution"],
        )
        exposures = data_api.get_exposures()
        particles = data_api.get_particles()

        _, fh_labels = extract_keys_with_foil_hole_averages(
            atlas_info,
            ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
            [],
            ["_rlnestimatedresolution"],
            exposures,
            particles,
        )

        epu_dir = Path(data_api.get_project().acquisition_directory)

        for gs in grid_squares:
            gs_dir = out_dir / gs.grid_square_name
            gs_dir.mkdir()
            thumbnail_path = epu_dir / gs.thumbnail
            shutil.copy(thumbnail_path, gs_dir / thumbnail_path.name)
            shutil.copy(
                thumbnail_path.with_suffix(".mrc"),
                gs_dir / thumbnail_path.with_suffix(".mrc").name,
            )
            out_gs_paths[gs.grid_square_name] = (
                gs_dir / thumbnail_path.name
            ).relative_to(out_dir)
        for fh in foil_holes:
            if all(fh_labels[dl].get(fh.foil_hole_name) for dl in data_labels):
                fh_dir = out_dir / fh.grid_square_name / fh.foil_hole_name
                fh_dir.mkdir()
                thumbnail_path = epu_dir / fh.thumbnail
                shutil.copy(thumbnail_path, fh_dir / thumbnail_path.name)
                shutil.copy(
                    thumbnail_path.with_suffix(".mrc"),
                    fh_dir / thumbnail_path.with_suffix(".mrc").name,
                )
                data["grid_square"].append(str(out_gs_paths[fh.grid_square_name]))
                data["foil_hole"].append(
                    str((fh_dir / thumbnail_path.name).relative_to(out_dir))
                )
                data["accummotiontotal"].append(
                    fh_labels["_rlnaccummotiontotal"][fh.foil_hole_name]
                )
                data["ctfmaxresolution"].append(
                    fh_labels["_rlnctfmaxresolution"][fh.foil_hole_name]
                )
                data["estimatedresolution"].append(
                    fh_labels["_rlnestimatedresolution"][fh.foil_hole_name]
                )

    df = DataFrame.from_dict(data)
    df.to_csv(out_dir / "labels.csv", index=False)
