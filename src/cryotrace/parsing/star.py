import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from gemmi import cif

from cryotrace.data_model import ExposureInfo, Particle, ParticleInfo
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
    extra_keys = [k for k in data.keys() if k and k not in (exposure_tag, x_tag, y_tag)]

    if validate:
        structured_data: Dict[str, Dict[str, list]] = {}
        for i, micrograph_path in enumerate(data[exposure_tag]):
            exposure_name = (
                Path(data[exposure_tag][i]).stem.replace("_fractions", "") + ".jpg"
            )
            if exposure_name in exposures:
                try:
                    structured_data[exposure_name]["coordinates"].append(
                        (data[x_tag][i], data[y_tag][i])
                    )
                    structured_data[exposure_name]["indices"].append(i)
                except KeyError:
                    structured_data[exposure_name] = {}
                    structured_data[exposure_name]["coordinates"] = [
                        (data[x_tag][i], data[y_tag][i])
                    ]
                    structured_data[exposure_name]["indices"] = [i]
        new_particles = []
        particle_info = []
        new_particle_indices: List[int] = []
        for exposure in exposures:
            existing_particles = extractor.get_particles(exposure)
            existing_particle_coords = {
                (ep.x, ep.y): ep.particle_id for ep in existing_particles
            }
            found_particles: Dict[int, int] = {}
            if structured_data.get(exposure):
                for i, particle in enumerate(structured_data[exposure]["coordinates"]):
                    if particle in existing_particle_coords.keys():
                        for k in extra_keys:
                            particle_info.append(
                                ParticleInfo(
                                    particle_id=existing_particle_coords[particle],
                                    source=star_file_path,
                                    key=k,
                                    value=data[k][
                                        structured_data[exposure]["indices"][i]
                                    ],
                                )
                            )
                        found_particles[
                            structured_data[exposure]["indices"][i]
                        ] = existing_particle_coords[particle]
                    else:
                        new_particles.append(
                            Particle(
                                x=particle[0], y=particle[1], exposure_name=exposure
                            )
                        )
                        new_particle_indices.append(
                            structured_data[exposure]["indices"][i]
                        )
        extractor.put_particles(new_particles)
        for k in extra_keys:
            for p, pind in zip(new_particles, new_particle_indices):
                particle_info.append(
                    ParticleInfo(
                        particle_id=p.particle_id,
                        source=star_file_path,
                        key=k,
                        value=data[k][pind],
                    )
                )
        if particle_info:
            extractor.put_info(particle_info)
