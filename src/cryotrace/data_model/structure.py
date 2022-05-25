from typing import Dict, List, Tuple

import numpy as np

from cryotrace.data_model import Base, Exposure, Particle


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
    unused_indices = {}
    indices = {}

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
            flat_counts[key] = np.full(len(exposures), 0)
            flat_results[key] = np.full(len(exposures), 0)
        else:
            flat_results[key] = np.full(len(exposures), None)
    for sr in sql_result:
        particle_tab_index = _particle_tab_index(sr)
        exposure_tab_index = _exposure_tab_index(sr)
        if use_particles:
            particle_index = indices[sr[particle_tab_index].particle_id]
            flat_results[sr[0].key][particle_index] = sr[0].value
            unused_indices[sr[particle_tab_index].particle_id][
                keys.index(sr[0].key)
            ] = True
        else:
            exposure_index = indices[sr[exposure_tab_index].exposure_name]
            if avg_particles:
                flat_results[sr[0].key][exposure_index] += sr[0].value
                flat_counts[sr[0].key][exposure_index] += 1
            else:
                flat_results[sr[0].key][exposure_index] = sr[0].value
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
) -> Tuple[Dict[str, List[float]], Dict[str, float]]:
    keys = exposure_keys + particle_keys + particle_set_keys
    avg_particles = bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    use_particles = not bool(exposure_keys) and (
        bool(particle_keys) or bool(particle_set_keys)
    )
    flat_results = {}
    flat_counts = {}
    unused_indices = {}
    indices = {}
    foil_hole_sums = {}
    foil_hole_counts = {}
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
            flat_counts[key] = np.full(len(exposures), 0)
            flat_results[key] = np.full(len(exposures), 0)
        else:
            flat_results[key] = np.full(len(exposures), None)
    for sr in sql_result:
        particle_tab_index = _particle_tab_index(sr)
        exposure_tab_index = _exposure_tab_index(sr)
        if use_particles:
            particle_index = indices[sr[particle_tab_index].particle_id]
            flat_results[sr[0].key][particle_index] = sr[0].value
            unused_indices[sr[particle_tab_index].particle_id][
                keys.index(sr[0].key)
            ] = True
        else:
            exposure_index = indices[sr[-1].exposure_name]
            if avg_particles:
                flat_results[sr[0].key][exposure_index] += sr[0].value
                flat_counts[sr[0].key][exposure_index] += 1
            else:
                flat_results[sr[0].key][exposure_index] = sr[0].value
            unused_indices[sr[exposure_tab_index].exposure_name][
                keys.index(sr[0].key)
            ] = True
        try:
            foil_hole_sums[sr[exposure_tab_index].foil_hole_name] += sr[0].value
            foil_hole_counts[sr[exposure_tab_index].foil_hole_name] += 1
        except KeyError:
            foil_hole_sums[sr[exposure_tab_index].foil_hole_name] = sr[0].value
            foil_hole_counts[sr[exposure_tab_index].foil_hole_name] = 1
    foil_hole_averages = {
        fh: foil_hole_sums[fh] / foil_hole_counts[fh] for fh in foil_hole_sums.keys()
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
