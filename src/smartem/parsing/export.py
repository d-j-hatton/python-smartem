import shutil
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import yaml
from pandas import DataFrame

from smartem.data_model import GridSquare
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import extract_keys_with_foil_hole_averages
from smartem.parsing.epu import calibrate_coordinate_system, mask_foil_hole_positions


def get_dataframe(
    data_api: DataAPI,
    projects: List[str],
    grid_squares: Optional[List[GridSquare]] = None,
    out_gs_paths: Optional[Dict[str, Path]] = None,
    out_fh_paths: Optional[Dict[str, Path]] = None,
    data_labels: Optional[List[str]] = None,
    use_adjusted_stage: bool = False,
) -> DataFrame:
    out_gs_paths = out_gs_paths or {}
    out_fh_paths = out_fh_paths or {}
    data: Dict[str, list] = {
        "grid_square": [],
        "grid_square_pixel_size": [],
        "grid_square_x": [],
        "grid_square_y": [],
        "foil_hole": [],
        "foil_hole_pixel_size": [],
        "foil_hole_x": [],
        "foil_hole_y": [],
        "accummotiontotal": [],
        "ctfmaxresolution": [],
        "estimatedresolution": [],
        "maxvalueprobdistribution": [],
    }
    for project in projects:
        _grid_squares = grid_squares or data_api.get_grid_squares(project)
        foil_holes = data_api.get_foil_holes(project=project)

        _data_labels = data_labels or [
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

        gs_coordinates = {}
        gs_pixel_sizes = {}

        for gs in _grid_squares:
            if gs.thumbnail:
                thumbnail_path: Optional[Path] = epu_dir / gs.thumbnail
                gs_coordinates[gs.grid_square_name] = (
                    gs.stage_position_x,
                    gs.stage_position_y,
                )
                gs_pixel_sizes[gs.grid_square_name] = gs.pixel_size
                if not out_gs_paths.get(gs.grid_square_name) and thumbnail_path:
                    out_gs_paths[gs.grid_square_name] = thumbnail_path

        for fh in foil_holes:
            if all(
                fh_extracted[dl].averages is not None for dl in _data_labels
            ):  # mypy doesn't accept this as good enough for the below
                if (
                    all(
                        fh_extracted[dl].averages.get(fh.foil_hole_name)  # type: ignore
                        for dl in _data_labels
                    )
                    # and fh.thumbnail
                ):
                    thumbnail_path = None
                    if fh.thumbnail:
                        thumbnail_path = epu_dir / fh.thumbnail
                    data["grid_square"].append(str(out_gs_paths[fh.grid_square_name]))
                    data["grid_square_pixel_size"].append(
                        gs_pixel_sizes[fh.grid_square_name]
                    )
                    data["grid_square_x"].append(gs_coordinates[fh.grid_square_name][0])
                    data["grid_square_y"].append(gs_coordinates[fh.grid_square_name][1])
                    data["foil_hole"].append(
                        str(out_fh_paths.get(fh.foil_hole_name) or thumbnail_path)
                    )
                    #     str((fh_dir / thumbnail_path.name).relative_to(out_dir))
                    #     if thumbnail_path
                    #     else None
                    # )
                    data["foil_hole_pixel_size"].append(fh.pixel_size)
                    if use_adjusted_stage:
                        data["foil_hole_x"].append(
                            fh.stage_position_x
                            if fh.adjusted_stage_position_x is None
                            else fh.adjusted_stage_position_x
                        )
                        data["foil_hole_y"].append(
                            fh.stage_position_y
                            if fh.adjusted_stage_position_y is None
                            else fh.adjusted_stage_position_y
                        )
                    else:
                        data["foil_hole_x"].append(fh.stage_position_x)
                        data["foil_hole_y"].append(fh.stage_position_y)
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

    return DataFrame.from_dict(data)


def export_foil_holes(
    data_api: DataAPI,
    out_dir: Path = Path("."),
    projects: Optional[List[str]] = None,
    use_adjusted_stage: bool = False,
    foil_hole_masks: bool = True,
    alternative_extension: str = "",
):
    if not projects:
        projects = [data_api._project]
    out_gs_paths = {}
    data: Dict[str, list] = {
        "grid_square": [],
        "grid_square_pixel_size": [],
        "grid_square_x": [],
        "grid_square_y": [],
        "foil_hole": [],
        "foil_hole_pixel_size": [],
        "foil_hole_x": [],
        "foil_hole_y": [],
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
        metadata_path = epu_dir.parent / "Metadata"

        if not atlas.thumbnail:
            raise ValueError(f"No atlas image was found for {project}")
        atlas_image_path = Path(atlas.thumbnail)
        shutil.copy(atlas_image_path, out_dir / atlas_image_path.name)
        shutil.copy(
            atlas_image_path.with_suffix(".mrc"),
            out_dir / atlas_image_path.with_suffix(".mrc").name,
        )

        gs_coordinates = {}
        gs_pixel_sizes = {}

        for gs in grid_squares:
            if gs.thumbnail:
                gs_dir = out_dir / gs.grid_square_name
                gs_dir.mkdir()
                thumbnail_path: Optional[Path] = epu_dir / gs.thumbnail
                if thumbnail_path:
                    shutil.copy(thumbnail_path, gs_dir / thumbnail_path.name)
                    shutil.copy(
                        thumbnail_path.with_suffix(alternative_extension or ".mrc"),
                        gs_dir
                        / thumbnail_path.with_suffix(
                            alternative_extension or ".mrc"
                        ).name,
                    )
                    out_gs_paths[gs.grid_square_name] = (
                        gs_dir / thumbnail_path.name
                    ).relative_to(out_dir)
                gs_coordinates[gs.grid_square_name] = (
                    gs.stage_position_x,
                    gs.stage_position_y,
                )
                gs_pixel_sizes[gs.grid_square_name] = gs.pixel_size
                if (
                    foil_hole_masks
                    and gs.grid_square_name
                    and gs.readout_area_x
                    and gs.readout_area_y
                    and thumbnail_path
                ):
                    mask = mask_foil_hole_positions(
                        metadata_path / f"{gs.grid_square_name}.dm",
                        (gs.readout_area_x, gs.readout_area_y),
                    )
                    np.save(gs_dir / thumbnail_path.with_suffix("").name, mask)
        for fh in foil_holes:
            if all(
                fh_extracted[dl].averages is not None for dl in data_labels
            ):  # mypy doesn't accept this as good enough for the below
                if (
                    all(
                        fh_extracted[dl].averages.get(fh.foil_hole_name)  # type: ignore
                        for dl in data_labels
                    )
                    # and fh.thumbnail
                ):
                    thumbnail_path = None
                    if fh.thumbnail:
                        fh_dir = out_dir / fh.grid_square_name / fh.foil_hole_name
                        fh_dir.mkdir()
                        thumbnail_path = epu_dir / fh.thumbnail
                        shutil.copy(thumbnail_path, fh_dir / thumbnail_path.name)
                        shutil.copy(
                            thumbnail_path.with_suffix(alternative_extension or ".mrc"),
                            fh_dir
                            / thumbnail_path.with_suffix(
                                alternative_extension or ".mrc"
                            ).name,
                        )
                    data["grid_square"].append(str(out_gs_paths[fh.grid_square_name]))
                    data["grid_square_pixel_size"].append(
                        gs_pixel_sizes[fh.grid_square_name]
                    )
                    data["grid_square_x"].append(gs_coordinates[fh.grid_square_name][0])
                    data["grid_square_y"].append(gs_coordinates[fh.grid_square_name][1])
                    data["foil_hole"].append(
                        str((fh_dir / thumbnail_path.name).relative_to(out_dir))
                        if thumbnail_path
                        else None
                    )
                    data["foil_hole_pixel_size"].append(fh.pixel_size)
                    if use_adjusted_stage:
                        data["foil_hole_x"].append(
                            fh.stage_position_x
                            if fh.adjusted_stage_position_x is None
                            else fh.adjusted_stage_position_x
                        )
                        data["foil_hole_y"].append(
                            fh.stage_position_y
                            if fh.adjusted_stage_position_y is None
                            else fh.adjusted_stage_position_y
                        )
                    else:
                        data["foil_hole_x"].append(fh.stage_position_x)
                        data["foil_hole_y"].append(fh.stage_position_y)
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

    if projects:
        _project = data_api.get_project(project_name=projects[0])
        for dm in (Path(_project.acquisition_directory).parent / "Metadata").glob(
            "*.dm"
        ):
            stage_calibration = calibrate_coordinate_system(dm)
            if stage_calibration:
                with open(out_dir / "coordinate_calibration.yaml", "w") as outfile:
                    yaml.dump(stage_calibration._asdict(), outfile)
                break
