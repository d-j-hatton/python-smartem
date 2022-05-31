from pathlib import Path

from smartem.data_model.extract import DataAPI
from smartem.parsing.star import (
    get_column_data,
    insert_exposure_data,
    insert_particle_set,
    open_star_file,
)


def _motion_corr(relion_dir: Path, data_handler: DataAPI):
    mc_file_path = relion_dir / "MotionCorr" / "job002" / "corrected_micrographs.star"
    star_file = open_star_file(mc_file_path)
    column_data = get_column_data(
        star_file, ["_rlnmicrographname", "_rlnaccummotiontotal"], "micrographs"
    )
    insert_exposure_data(
        column_data, "_rlnmicrographname", str(mc_file_path), data_handler
    )


def _ctf(relion_dir: Path, data_handler: DataAPI):
    ctf_file_path = relion_dir / "CtfFind" / "job006" / "micrographs_ctf.star"
    star_file = open_star_file(ctf_file_path)
    column_data = get_column_data(
        star_file, ["_rlnmicrographname", "_rlnctfmaxresolution"], "micrographs"
    )
    insert_exposure_data(
        column_data, "_rlnmicrographname", str(ctf_file_path), data_handler
    )


def _class2d(relion_dir: Path, data_handler: DataAPI):
    for class_file_path in (relion_dir / "Class2D").glob("job*"):
        star_file = open_star_file(class_file_path / "run_it020_data.star")
        cross_ref_star_file = open_star_file(class_file_path / "run_it020_model.star")
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
            add_source_to_id=True,
        )


def gather_relion_defaults(relion_dir: Path, data_handler: DataAPI):
    _motion_corr(relion_dir, data_handler)
    _ctf(relion_dir, data_handler)
    _class2d(relion_dir, data_handler)
