import math
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

import numpy as np
from sqlalchemy.engine.row import LegacyRow

from smartem.data_model import Base, Exposure, FoilHole, Particle


class ExtractedData(NamedTuple):
    flattened_data: List[float]
    averages: Optional[Dict[str, float]] = None
    counts: Optional[Dict[str, int]] = None


def _particle_tab_index(tables: Tuple[Base], default: int = -2) -> int:
    pti = default
    for i, r in enumerate(tables):
        if isinstance(r, Particle):
            pti = i
            break
    return pti


def _exposure_tab_index(tables: Tuple[Base], default: int = -1) -> int:
    eti = default
    for i, r in enumerate(tables):
        if isinstance(r, Exposure):
            eti = i
            break
    return eti


def _foil_hole_tab_index(tables: Tuple[Base], default: int = -1) -> int:
    fhti = default
    for i, r in enumerate(tables):
        if isinstance(r, FoilHole):
            fhti = i
            break
    return fhti


def extract_keys(
    sql_result: list,
    exposure_keys: List[str],
    particle_keys: List[str],
    particle_set_keys: List[str],
) -> Dict[str, List[float]]:
    particles = {sr[_particle_tab_index(sr)] for sr in sql_result}
    exposures = {sr[_exposure_tab_index(sr)] for sr in sql_result}
    keys = exposure_keys + particle_keys + particle_set_keys
    avg_particles = bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    use_particles = not bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    flat_results = {}
    flat_counts = {}
    unused_indices: Dict[Union[int, str], List[bool]] = {}
    indices: Dict[Union[int, str], int] = {}

    if use_particles:
        for i, p in enumerate(particles):
            unused_indices[p.particle_id] = [False for _ in keys]
            indices[p.particle_id] = i
    else:
        for i, exp in enumerate(exposures):
            unused_indices[exp.exposure_name] = [False for _ in keys]
            indices[exp.exposure_name] = i
    for key in keys:
        if use_particles:
            flat_results[key] = np.full(len(particles), None)
        elif avg_particles:
            flat_counts[key] = np.full(len(exposures), 0.0)
            flat_results[key] = np.full(len(exposures), 0.0)
        else:
            flat_results[key] = np.full(len(exposures), None)
    for sr in sql_result:
        particle_tab_index = _particle_tab_index(sr)
        exposure_tab_index = _exposure_tab_index(sr)
        if use_particles:
            particle_index = indices[sr[particle_tab_index].particle_id]
            if not math.isinf(sr[0].value):
                flat_results[sr[0].key][particle_index] = sr[0].value
                unused_indices[sr[particle_tab_index].particle_id][
                    keys.index(sr[0].key)
                ] = True
        else:
            exposure_index = indices[sr[exposure_tab_index].exposure_name]
            if avg_particles:
                if not math.isinf(sr[0].value):
                    flat_results[sr[0].key][exposure_index] += sr[0].value
                    flat_counts[sr[0].key][exposure_index] += 1
            else:
                if not math.isinf(sr[0].value):
                    flat_results[sr[0].key][exposure_index] = sr[0].value
            if not math.isinf(sr[0].value):
                unused_indices[sr[exposure_tab_index].exposure_name][
                    keys.index(sr[0].key)
                ] = True

    collated_unused_indices = [k for k, v in unused_indices.items() if not all(v)]
    indices_for_deletion = [indices[i] for i in collated_unused_indices]
    for key in keys:
        flat_results[key] = np.delete(flat_results[key], indices_for_deletion)
        if avg_particles:
            flat_counts[key] = np.delete(flat_counts[key], indices_for_deletion)
    if avg_particles:
        for k, v in flat_results.items():
            flat_results[k] = np.divide(v, flat_counts[k])
    return flat_results


def extract_keys_with_foil_hole_averages(
    sql_result: List[LegacyRow],
    exposure_keys: List[str],
    particle_keys: List[str],
    particle_set_keys: List[str],
    limits: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Dict[str, ExtractedData]:
    limits = limits or {}
    particles = {sr.particle_id for sr in sql_result if hasattr(sr, "particle_id")}
    exposures = {sr.exposure_name for sr in sql_result}
    keys = exposure_keys + particle_keys + particle_set_keys
    avg_particles = bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    use_particles = not bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    flat_results = {}
    flat_counts = {}
    unused_indices: Dict[Union[int, str], List[bool]] = {}
    indices: Dict[Union[int, str], int] = {}
    foil_hole_sums: Dict[str, Dict[str, float]] = {}
    foil_hole_counts: Dict[str, Dict[str, int]] = {}
    if use_particles:
        for i, p in enumerate(particles):
            unused_indices[p] = [False for _ in keys]
            indices[p] = i
    else:
        for i, exp in enumerate(exposures):
            unused_indices[exp] = [False for _ in keys]
            indices[exp] = i
    for key in keys:
        foil_hole_sums[key] = {}
        foil_hole_counts[key] = {}
        if use_particles:
            flat_results[key] = np.full(len(particles), None)
        elif avg_particles:
            flat_counts[key] = np.full(len(exposures), 0.0)
            flat_results[key] = np.full(len(exposures), 0.0)
        else:
            flat_results[key] = np.full(len(exposures), None)
    for sr in sql_result:
        current_bound = limits.get(sr.key, (-np.inf, np.inf))
        if sr.value > current_bound[0] and sr.value < current_bound[1]:
            if use_particles:
                particle_index = indices[sr.particle_id]
                if not math.isinf(sr.value):
                    flat_results[sr.key][particle_index] = sr.value
                    unused_indices[sr.particle_id][keys.index(sr.key)] = True
            else:
                exposure_index = indices[sr.exposure_name]
                if avg_particles:
                    if not math.isinf(sr.value):
                        flat_results[sr.key][exposure_index] += sr.value
                        flat_counts[sr.key][exposure_index] += 1
                else:
                    if not math.isinf(sr.value):
                        flat_results[sr.key][exposure_index] = sr.value
                if not math.isinf(sr.value):
                    unused_indices[sr.exposure_name][keys.index(sr.key)] = True
            try:
                if not math.isinf(sr.value):
                    foil_hole_sums[sr.key][sr.foil_hole_name] += sr.value
                    foil_hole_counts[sr.key][sr.foil_hole_name] += 1
            except KeyError:
                if not math.isinf(sr.value):
                    foil_hole_sums[sr.key][sr.foil_hole_name] = sr.value
                    foil_hole_counts[sr.key][sr.foil_hole_name] = 1
    foil_hole_averages = {}
    for k in keys:
        foil_hole_averages[k] = {
            fh: foil_hole_sums[k][fh] / foil_hole_counts[k][fh]
            for fh in foil_hole_sums[k].keys()
        }
    collated_unused_indices = [k for k, v in unused_indices.items() if not all(v)]
    indices_for_deletion = [indices[i] for i in collated_unused_indices]
    for key in keys:
        flat_results[key] = np.delete(flat_results[key], indices_for_deletion)
        if avg_particles:
            flat_counts[key] = np.delete(flat_counts[key], indices_for_deletion)
    if avg_particles:
        for k, v in flat_results.items():
            flat_results[k] = np.divide(v, flat_counts[k])
    extracted_data = {
        k: ExtractedData(
            flattened_data=flat_results[k],
            averages=foil_hole_averages[k],
            counts=foil_hole_counts[k],
        )
        for k in keys
    }
    return extracted_data


def extract_keys_with_grid_square_averages(
    sql_result: List[LegacyRow],
    exposure_keys: List[str],
    particle_keys: List[str],
    particle_set_keys: List[str],
) -> Dict[str, ExtractedData]:
    particles = {sr.particle_id for sr in sql_result if hasattr(sr, "particle_id")}
    exposures = {sr.exposure_name for sr in sql_result}
    keys = exposure_keys + particle_keys + particle_set_keys
    avg_particles = bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    use_particles = not bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    flat_results = {}
    flat_counts = {}
    unused_indices: Dict[Union[int, str], List[bool]] = {}
    indices: Dict[Union[int, str], int] = {}
    grid_square_sums: Dict[str, Dict[str, float]] = {}
    grid_square_counts: Dict[str, Dict[str, int]] = {}
    if use_particles:
        for i, p in enumerate(particles):
            unused_indices[p] = [False for _ in keys]
            indices[p] = i
    else:
        for i, exp in enumerate(exposures):
            unused_indices[exp] = [False for _ in keys]
            indices[exp] = i
    for key in keys:
        grid_square_counts[key] = {}
        grid_square_sums[key] = {}
        if use_particles:
            flat_results[key] = np.full(len(particles), None)
        elif avg_particles:
            flat_counts[key] = np.full(len(exposures), 0.0)
            flat_results[key] = np.full(len(exposures), 0.0)
        else:
            flat_results[key] = np.full(len(exposures), None)
    for sr in sql_result:
        if use_particles:
            particle_index = indices[sr.particle_id]
            if not math.isinf(sr.value):
                flat_results[sr.key][particle_index] = sr.value
                unused_indices[sr.particle_id][keys.index(sr.key)] = True
        else:
            exposure_index = indices[sr.exposure_name]
            if avg_particles:
                if not math.isinf(sr.value):
                    flat_results[sr.key][exposure_index] += sr.value
                    flat_counts[sr.key][exposure_index] += 1
            else:
                if not math.isinf(sr.value):
                    flat_results[sr.key][exposure_index] = sr.value
            if not math.isinf(sr.value):
                unused_indices[sr.exposure_name][keys.index(sr.key)] = True
        try:
            if not math.isinf(sr.value):
                grid_square_sums[sr.key][sr.grid_square_name] += sr.value
                grid_square_counts[sr.key][sr.grid_square_name] += 1
        except KeyError:
            if not math.isinf(sr.value):
                grid_square_sums[sr.key][sr.grid_square_name] = sr.value
                grid_square_counts[sr.key][sr.grid_square_name] = 1
    grid_square_averages = {}
    for k in keys:
        grid_square_averages[k] = {
            gs: grid_square_sums[k][gs] / grid_square_counts[k][gs]
            for gs in grid_square_sums[k].keys()
        }
    collated_unused_indices = [k for k, v in unused_indices.items() if not all(v)]
    indices_for_deletion = [indices[i] for i in collated_unused_indices]
    for key in keys:
        flat_results[key] = np.delete(flat_results[key], indices_for_deletion)
        if avg_particles:
            flat_counts[key] = np.delete(flat_counts[key], indices_for_deletion)
    if avg_particles:
        for k, v in flat_results.items():
            flat_results[k] = np.divide(v, flat_counts[k])
    extracted_data = {
        k: ExtractedData(
            flattened_data=flat_results[k],
            averages=grid_square_averages[k],
            counts=grid_square_counts[k],
        )
        for k in keys
    }
    return extracted_data
