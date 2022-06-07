import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from gemmi import cif

from smartem.data_model import (
    ExposureInfo,
    Particle,
    ParticleInfo,
    ParticleSet,
    ParticleSetInfo,
    ParticleSetLinker,
)
from smartem.data_model.extract import DataAPI


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
    extractor: DataAPI,
    validate: bool = True,
    extra_suffix: str = "",
):
    if validate:
        exposures = [e.exposure_name for e in extractor.get_exposures()]
    exposure_info: List[ExposureInfo] = []
    for k, v in data.items():
        if k != exposure_tag:
            for i, value in enumerate(v):
                exposure_name = (
                    Path(data[exposure_tag][i])
                    .stem.replace("_fractions", "")
                    .replace("_Fractions", "")
                    .replace(extra_suffix, "")
                    + ".jpg"
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

    extractor.put(exposure_info)


def _structure_particle_data(
    data: Dict[str, List[str]],
    exposures: List[str],
    exposure_tag: str,
    x_tag: str,
    y_tag: str,
) -> Dict[str, Dict[str, list]]:
    structured_data: Dict[str, Dict[str, list]] = {}
    for i, micrograph_path in enumerate(data[exposure_tag]):
        exposure_name = (
            Path(micrograph_path)
            .stem.replace("_fractions", "")
            .replace("_Fractions", "")
            + ".jpg"
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
    return structured_data


def insert_particle_data(
    data: Dict[str, List[str]],
    exposure_tag: str,
    x_tag: str,
    y_tag: str,
    star_file_path: str,
    extractor: DataAPI,
) -> List[Particle]:
    exposures = [e.exposure_name for e in extractor.get_exposures()]
    particle_info: List[ParticleInfo] = []
    extra_keys = [k for k in data.keys() if k and k not in (exposure_tag, x_tag, y_tag)]

    structured_data = _structure_particle_data(
        data, exposures, exposure_tag, x_tag, y_tag
    )

    all_particles = []
    new_particles = []
    particle_info = []
    new_particle_indices: List[int] = []
    for exposure in exposures:
        existing_particles = extractor.get_particles(exposure_name=exposure)
        all_particles.extend(existing_particles)
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
                                value=data[k][structured_data[exposure]["indices"][i]],
                            )
                        )
                    found_particles[
                        structured_data[exposure]["indices"][i]
                    ] = existing_particle_coords[particle]
                else:
                    new_particles.append(
                        Particle(x=particle[0], y=particle[1], exposure_name=exposure)
                    )
                    new_particle_indices.append(structured_data[exposure]["indices"][i])
    extractor.put(new_particles)
    all_particles.extend(new_particles)
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
        extractor.put(particle_info)
    return all_particles


def insert_particle_set(
    data: Dict[str, List[str]],
    set_name: str,
    set_id_tag: str,
    exposure_tag: str,
    x_tag: str,
    y_tag: str,
    star_file_path: str,
    extractor: DataAPI,
    add_source_to_id: bool = False,
):
    extra_keys = [
        k
        for k in data.keys()
        if k and k not in (exposure_tag, x_tag, y_tag, set_id_tag)
    ]
    set_ids = set(data[set_id_tag])
    _particle_sets = extractor.get_particle_sets(set_name, set_ids, star_file_path)
    if not _particle_sets:
        if add_source_to_id:
            particle_sets = [
                ParticleSet(
                    group_name=set_name,
                    identifier=star_file_path + ":" + str(set_id),
                    project_name=extractor._project,
                )
                for set_id in set_ids
            ]
        else:
            particle_sets = [
                ParticleSet(
                    group_name=set_name,
                    identifier=str(set_id),
                    project_name=extractor._project,
                )
                for set_id in set_ids
            ]
        extractor.put(particle_sets)
    else:
        particle_sets = []
        for set_id in set_ids:
            for ps in _particle_sets:
                if ps.identifier == set_id:
                    particle_sets.append(ps)
    exposures = [e.exposure_name for e in extractor.get_exposures()]
    structured_data = _structure_particle_data(
        data, exposures, exposure_tag, x_tag, y_tag
    )
    set_instances: Dict[str, Dict[str, float]] = {}
    linkers = []
    new_particles = []
    linkers_for_new_particles = []

    if extra_keys:
        for si in set_ids:
            for i, s in enumerate(data[set_id_tag]):
                if s == si:
                    set_instances[si] = {
                        k: float(v[i]) for k, v in data.items() if k in extra_keys
                    }
                    break

    for exposure in exposures:
        if structured_data.get(exposure):
            particles = extractor.get_particles(exposure_name=exposure)
            particle_coords = {(p.x, p.y): p.particle_id for p in particles}
            for i, particle in enumerate(structured_data[exposure]["coordinates"]):
                if particle_coords.get(particle):
                    if not _particle_sets:
                        if add_source_to_id:
                            linkers.append(
                                ParticleSetLinker(
                                    set_name=star_file_path
                                    + ":"
                                    + str(
                                        data[set_id_tag][
                                            structured_data[exposure]["indices"][i]
                                        ]
                                    ),
                                    particle_id=particle_coords[particle],
                                )
                            )
                        else:
                            linkers.append(
                                ParticleSetLinker(
                                    set_name=data[set_id_tag][
                                        structured_data[exposure]["indices"][i]
                                    ],
                                    particle_id=particle_coords[particle],
                                )
                            )
                else:
                    new_particles.append(
                        Particle(x=particle[0], y=particle[1], exposure_name=exposure)
                    )

    if linkers:
        extractor.put(linkers)

    if new_particles:
        extractor.put(new_particles)

        for exposure in exposures:
            if structured_data.get(exposure):
                particle_coords = {
                    (p.x, p.y): p.particle_id
                    for p in new_particles
                    if p.exposure_name == exposure
                }
                for i, particle in enumerate(structured_data[exposure]["coordinates"]):
                    if particle_coords.get(particle):
                        if add_source_to_id:
                            linkers_for_new_particles.append(
                                ParticleSetLinker(
                                    set_name=star_file_path
                                    + ":"
                                    + str(
                                        data[set_id_tag][
                                            structured_data[exposure]["indices"][i]
                                        ]
                                    ),
                                    particle_id=particle_coords[particle],
                                )
                            )
                        else:
                            linkers_for_new_particles.append(
                                ParticleSetLinker(
                                    set_name=data[set_id_tag][
                                        structured_data[exposure]["indices"][i]
                                    ],
                                    particle_id=particle_coords[particle],
                                )
                            )
        if linkers_for_new_particles:
            extractor.put(linkers_for_new_particles)

    particle_set_info = []
    for k in extra_keys:
        for si in set_ids:
            if add_source_to_id:
                particle_set_info.append(
                    ParticleSetInfo(
                        set_name=star_file_path + ":" + str(si),
                        source=star_file_path,
                        key=k,
                        value=set_instances[si][k],
                    )
                )
            else:
                particle_set_info.append(
                    ParticleSetInfo(
                        set_name=si,
                        source=star_file_path,
                        key=k,
                        value=set_instances[si][k],
                    )
                )
    if particle_set_info:
        extractor.put(particle_set_info)
