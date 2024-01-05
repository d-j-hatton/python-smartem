from pathlib import Path
from typing import Dict, List, Optional

from numpy import argmin

from smartem.data_model.extract import DataAPI
from smartem.parsing.star import (
    get_column_data,
    insert_exposure_data,
    insert_particle_data,
    insert_particle_set,
    open_star_file,
)


def _motion_corr(relion_dir: Path, data_handler: DataAPI, project: str):
    mc_base_path = relion_dir / "MotionCorr"
    mc_file_job_paths = mc_base_path.glob("job*")
    job_numbers = [str(j.name).replace("job", "") for j in mc_file_job_paths]
    first_job_idx = argmin([int(jn) for jn in job_numbers])
    mc_file_path = (
        relion_dir
        / "MotionCorr"
        / f"job{job_numbers[first_job_idx]}"
        / "corrected_micrographs.star"
    )
    star_file = open_star_file(mc_file_path)
    column_data = get_column_data(
        star_file, ["_rlnmicrographname", "_rlnaccummotiontotal"], "micrographs"
    )
    insert_exposure_data(
        column_data,
        "_rlnmicrographname",
        str(mc_file_path),
        data_handler,
        project=project,
    )


def _ctf(relion_dir: Path, data_handler: DataAPI, project: str):
    ctf_base_path = relion_dir / "CtfFind"
    ctf_file_job_paths = ctf_base_path.glob("job*")
    job_numbers = [str(j.name).replace("job", "") for j in ctf_file_job_paths]
    first_job_idx = argmin([int(jn) for jn in job_numbers])
    ctf_file_path = (
        relion_dir
        / "CtfFind"
        / f"job{job_numbers[first_job_idx]}"
        / "micrographs_ctf.star"
    )
    star_file = open_star_file(ctf_file_path)
    column_data = get_column_data(
        star_file, ["_rlnmicrographname", "_rlnctfmaxresolution"], "micrographs"
    )
    insert_exposure_data(
        column_data,
        "_rlnmicrographname",
        str(ctf_file_path),
        data_handler,
        project=project,
    )


def _num_particles(relion_dir: Path, data_handler: DataAPI, project: str):
    picking_base_path = relion_dir / "AutoPick"
    picking_file_job_paths = picking_base_path.glob("job*")
    job_numbers = [str(j.name).replace("job", "") for j in picking_file_job_paths]
    first_job_idx = argmin([int(jn) for jn in job_numbers])
    picking_file_path = (
        relion_dir / "AutoPick" / f"job{job_numbers[first_job_idx]}" / "autopick.star"
    )
    star_file = open_star_file(picking_file_path)
    column_data = get_column_data(
        star_file,
        ["_rlnmicrographname", "_rlnmicrographcoordinates"],
        "coordinate_files",
    )
    count_data: Dict[str, list] = {
        "_rlnmicrographname": [],
        "_rlnmicrographparticlecount": [],
    }
    for mic, cfile in zip(
        column_data["_rlnmicrographname"], column_data["_rlnmicrographcoordinates"]
    ):
        if not (relion_dir / cfile).is_file():
            continue
        coord_file = open_star_file(relion_dir / cfile)
        coord_column_data = get_column_data(coord_file, ["_rlncoordinatex"], "#")
        count_data["_rlnmicrographname"].append(mic)
        count_data["_rlnmicrographparticlecount"].append(
            len(coord_column_data["_rlncoordinatex"])
        )
    insert_exposure_data(
        count_data,
        "_rlnmicrographname",
        str(picking_file_path),
        data_handler,
        project=project,
    )


def _prob_dist_max_class2d(
    relion_dir: Path,
    data_handler: DataAPI,
    project: str,
    excluded_directories: Optional[List[str]] = None,
):
    exclude = excluded_directories or []
    for class_file_path in (relion_dir / "Class2D").glob("job*"):
        if class_file_path.name not in exclude:
            star_file = open_star_file(class_file_path / "run_it020_data.star")
            column_data = get_column_data(
                star_file,
                [
                    "_rlnmicrographname",
                    "_rlncoordinatex",
                    "_rlncoordinatey",
                    "_rlnmaxvalueprobdistribution",
                ],
                "particles",
            )
            insert_particle_data(
                column_data,
                "_rlnmicrographname",
                "_rlncoordinatex",
                "_rlncoordinatey",
                str(class_file_path / "run_it020_data.star"),
                data_handler,
                project=project,
            )


def _class2d(
    relion_dir: Path,
    data_handler: DataAPI,
    project: str,
    excluded_directories: Optional[List[str]] = None,
):
    exclude = excluded_directories or []
    for class_file_path in (relion_dir / "Class2D").glob("job*"):
        if class_file_path.name not in exclude:
            star_file = open_star_file(class_file_path / "run_it020_data.star")
            cross_ref_star_file = open_star_file(
                class_file_path / "run_it020_model.star"
            )
            column_data = get_column_data(
                star_file,
                [
                    "_rlnmicrographname",
                    "_rlncoordinatex",
                    "_rlncoordinatey",
                    "_rlnclassnumber",
                ],
                "particles",
            )
            cross_ref_column_data = get_column_data(
                cross_ref_star_file,
                ["_rlnreferenceimage", "_rlnestimatedresolution"],
                "model_classes",
            )
            for v in cross_ref_column_data.values():
                for i, elem in enumerate(v):
                    if isinstance(elem, str) and "@" in elem:
                        _elem = elem.split("@")[0]
                        while _elem.startswith("0"):
                            _elem = _elem[1:]
                        v[i] = _elem
            cross_ref_dict = {}
            for i, k02 in enumerate(column_data["_rlnclassnumber"]):
                for j, k01 in enumerate(cross_ref_column_data["_rlnreferenceimage"]):
                    if k01 == str(k02):
                        cross_ref_dict[i] = cross_ref_column_data[
                            "_rlnestimatedresolution"
                        ][j]
            column_data["_rlnestimatedresolution"] = [
                cross_ref_dict[i] for i in range(len(column_data["_rlnclassnumber"]))
            ]
            insert_particle_set(
                column_data,
                "class_2d",
                "_rlnclassnumber",
                "_rlnmicrographname",
                "_rlncoordinatex",
                "_rlncoordinatey",
                str(class_file_path / "run_it020_data.star"),
                data_handler,
                project,
                add_source_to_id=True,
            )


def gather_relion_defaults(
    relion_dir: Path,
    data_handler: DataAPI,
    project: str,
    class_2d_excludes: Optional[List[str]] = None,
):
    _motion_corr(relion_dir, data_handler, project)
    _ctf(relion_dir, data_handler, project)
    _num_particles(relion_dir, data_handler, project)
    _prob_dist_max_class2d(
        relion_dir, data_handler, project, excluded_directories=class_2d_excludes
    )
    _class2d(relion_dir, data_handler, project, excluded_directories=class_2d_excludes)
