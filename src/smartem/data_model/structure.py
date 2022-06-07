import math
from typing import Dict, List, Tuple, Union

import numpy as np

from smartem.data_model import Base, Exposure, FoilHole, Particle


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
    exposures: List[Exposure],
    particles: List[Particle],
) -> Dict[str, List[float]]:
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
    sql_result: list,
    exposure_keys: List[str],
    particle_keys: List[str],
    particle_set_keys: List[str],
    exposures: List[Exposure],
    particles: List[Particle],
) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
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
            unused_indices[p.particle_id] = [False for _ in keys]
            indices[p.particle_id] = i
    else:
        for i, exp in enumerate(exposures):
            unused_indices[exp.exposure_name] = [False for _ in keys]
            indices[exp.exposure_name] = i
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
            exposure_index = indices[sr[-1].exposure_name]
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
        try:
            if not math.isinf(sr[0].value):
                foil_hole_sums[sr[0].key][sr[exposure_tab_index].foil_hole_name] += sr[
                    0
                ].value
                foil_hole_counts[sr[0].key][sr[exposure_tab_index].foil_hole_name] += 1
        except KeyError:
            if not math.isinf(sr[0].value):
                foil_hole_sums[sr[0].key][sr[exposure_tab_index].foil_hole_name] = sr[
                    0
                ].value
                foil_hole_counts[sr[0].key][sr[exposure_tab_index].foil_hole_name] = 1
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
    return (flat_results, foil_hole_averages)


def extract_keys_with_grid_square_averages(
    sql_result: list,
    exposure_keys: List[str],
    particle_keys: List[str],
    particle_set_keys: List[str],
    exposures: List[Exposure],
    particles: List[Particle],
) -> Tuple[Dict[str, List[float]], Dict[str, Dict[str, float]]]:
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
            unused_indices[p.particle_id] = [False for _ in keys]
            indices[p.particle_id] = i
    else:
        for i, exp in enumerate(exposures):
            unused_indices[exp.exposure_name] = [False for _ in keys]
            indices[exp.exposure_name] = i
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
        particle_tab_index = _particle_tab_index(sr)
        exposure_tab_index = _exposure_tab_index(sr)
        foil_hole_tab_index = _foil_hole_tab_index(sr)
        if use_particles:
            particle_index = indices[sr[particle_tab_index].particle_id]
            if not math.isinf(sr[0].value):
                flat_results[sr[0].key][particle_index] = sr[0].value
                unused_indices[sr[particle_tab_index].particle_id][
                    keys.index(sr[0].key)
                ] = True
        else:
            exposure_index = indices[sr[-1].exposure_name]
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
        try:
            if not math.isinf(sr[0].value):
                grid_square_sums[sr[0].key][
                    sr[foil_hole_tab_index].grid_square_name
                ] += sr[0].value
                grid_square_counts[sr[0].key][
                    sr[foil_hole_tab_index].grid_square_name
                ] += 1
        except KeyError:
            if not math.isinf(sr[0].value):
                grid_square_sums[sr[0].key][
                    sr[foil_hole_tab_index].grid_square_name
                ] = sr[0].value
                grid_square_counts[sr[0].key][
                    sr[foil_hole_tab_index].grid_square_name
                ] = 1
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
    return (flat_results, grid_square_averages)
