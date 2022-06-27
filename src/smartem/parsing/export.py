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
        "maxvalueprobdistribution": [],
    }

    for project in projects:
        grid_squares = data_api.get_grid_squares(project)
        foil_holes = data_api.get_foil_holes(project=project)

        data_labels = [
            "_rlnaccummotiontotal",
            "_rlnctfmaxresolution",
            "_rlnestimatedresolution",
            "_rlnmaxvalueprobdistribution",
        ]

        _project = data_api.get_project(project_name=project)
        atlas = data_api.get_atlas_from_project(_project)
        atlas_id = atlas.atlas_id
        atlas_info = data_api.get_atlas_info(
            atlas_id,
            ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
            ["_rlnmaxvalueprobdistribution"],
            ["_rlnestimatedresolution"],
        )

        fh_extracted = extract_keys_with_foil_hole_averages(
            atlas_info,
            ["_rlnaccummotiontotal", "_rlnctfmaxresolution"],
            ["_rlnmaxvalueprobdistribution"],
            ["_rlnestimatedresolution"],
        )

        epu_dir = Path(_project.acquisition_directory)

        if not atlas.thumbnail:
            raise ValueError(f"No atlas image was found for {project}")
        atlas_image_path = Path(atlas.thumbnail)
        shutil.copy(atlas_image_path, out_dir / atlas_image_path.name)
        shutil.copy(
            atlas_image_path, out_dir / atlas_image_path.with_suffix(".mrc").name
        )

        for gs in grid_squares:
            if gs.thumbnail:
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
            if all(
                fh_extracted[dl].averages is not None for dl in data_labels
            ):  # mypy doesn't accept this as good enough for the below
                if (
                    all(
                        fh_extracted[dl].averages.get(fh.foil_hole_name)  # type: ignore
                        for dl in data_labels
                    )
                    and fh.thumbnail
                ):
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
                        fh_extracted["_rlnaccummotiontotal"].averages[fh.foil_hole_name]  # type: ignore
                    )
                    data["ctfmaxresolution"].append(
                        fh_extracted["_rlnctfmaxresolution"].averages[fh.foil_hole_name]  # type: ignore
                    )
                    data["estimatedresolution"].append(
                        fh_extracted["_rlnestimatedresolution"].averages[  # type: ignore
                            fh.foil_hole_name
                        ]
                    )
                    data["maxvalueprobdistribution"].append(
                        fh_extracted["_rlnmaxvalueprobdistribution"].averages[  # type: ignore
                            fh.foil_hole_name
                        ]
                    )

    df = DataFrame.from_dict(data)
    df.to_csv(out_dir / "labels.csv", index=False)
