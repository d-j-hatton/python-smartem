import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from gemmi import cif

from cryotrace.data_model import ExposureInfo, ParticleInfo
from cryotrace.data_model.extract import Extractor


def open_star_file(star_file_path: Path):
    gemmi_readable_path = os.fspath(star_file_path)
    return cif.read_file(gemmi_readable_path)


def get_columns(star_file, ignore: Optional[List[str]] = None) -> List[str]:
    json_star = json.loads(star_file.as_json())
    cols = []
    for v in json_star.values():
        if ignore:
            vals = [_v for _v in v.keys() if all(ig not in _v for ig in ignore)]
            cols.extend(vals)
        else:
            cols.extend(v.keys())
    return cols


def get_column_data(
    star_file, columns: List[str], block_tag: str
) -> Dict[str, List[str]]:
    json_star = json.loads(star_file.as_json())
    return {k: v for k, v in json_star[block_tag].items() if k in columns}


def insert_exposure_data(
    data: Dict[str, List[str]],
    exposure_tag: str,
    star_file_path: str,
    extractor: Extractor,
    validate: bool = True,
):
    if validate:
        exposures = [e.exposure_name for e in extractor.get_all_exposures()]
    exposure_info: List[ExposureInfo] = []
    for k, v in data.items():
        if k != exposure_tag:
            for i, value in enumerate(v):
                exposure_name = (
                    Path(data[exposure_tag][i]).stem.replace("_fractions", "") + ".jpg"
                )
                if validate:
                    if exposure_name in exposures:
                        exinf = ExposureInfo(
                            exposure_name=exposure_name,
                            source=star_file_path,
                            key=k,
                            value=value,
                        )
                        exposure_info.append(exinf)
                    else:
                        print(f"exposure {exposure_name} not found")
                else:
                    exinf = ExposureInfo(
                        exposure_name=exposure_name,
                        source=star_file_path,
                        key=k,
                        value=value,
                    )
                    exposure_info.append(exinf)

    extractor.put_info(exposure_info)


def insert_particle_data(
    data: Dict[str, List[str]],
    exposure_tag: str,
    x_tag: str,
    y_tag: str,
    star_file_path: str,
    extractor: Extractor,
    validate: bool = True,
    just_particles: bool = False,
):
    if validate:
        exposures = [e.exposure_name for e in extractor.get_all_exposures()]
    particle_info: List[ParticleInfo] = []
    for k, v in data.items():
        if just_particles:
            for i, value in enumerate(v):
                exposure_name = (
                    Path(data[exposure_tag][i]).stem.replace("_fractions", "") + ".jpg"
                )
                x = float(data[x_tag][i])
                y = float(data[y_tag][i])
                particle_id = extractor.get_particle_id(exposure_name, x, y)
                if particle_id is None:
                    if validate:
                        if exposure_name in exposures:
                            particle_id = extractor.put_particle(exposure_name, x, y)
                    else:
                        particle_id = extractor.put_particle(exposure_name, x, y)
        else:
            if k not in (exposure_tag, x_tag, y_tag):
                for i, value in enumerate(v):
                    exposure_name = (
                        Path(data[exposure_tag][i]).stem.replace("_fractions", "")
                        + ".jpg"
                    )
                    x = float(data[x_tag][i])
                    y = float(data[y_tag][i])
                    particle_id = extractor.get_particle_id(exposure_name, x, y)
                    if particle_id is None:
                        if validate:
                            if exposure_name in exposures:
                                particle_id = extractor.put_particle(
                                    exposure_name, x, y
                                )
                        else:
                            particle_id = extractor.put_particle(exposure_name, x, y)
                    if particle_id:
                        partinfo = ParticleInfo(
                            particle_id=particle_id,
                            source=star_file_path,
                            key=k,
                            value=value,
                        )
                        particle_info.append(partinfo)
    if not just_particles:
        extractor.put_info(particle_info)
