from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from cryotrace.data_model import (
    Exposure,
    FoilHole,
    InfoStore,
    Particle,
    ParticleSetLinker,
)


def grid_square_strucutre(
    sql_result: List[
        Union[
            Tuple[InfoStore, Exposure, FoilHole],
            Tuple[InfoStore, Particle, Exposure, FoilHole],
            Tuple[InfoStore, ParticleSetLinker, Particle, Exposure, FoilHole],
        ]
    ],
    keys: List[str],
    grid_square_exposures: Dict[str, str],
) -> Dict[str, Dict[str, List[Optional[float]]]]:
    structured_res: Dict[str, Dict[str, List[Optional[float]]]] = {k: {} for k in keys}
    gs_indices: Dict[str, Dict[str, int]] = {k: {} for k in keys}
    for k in keys:
        for gs, exps in grid_square_exposures.items():
            l = len(exps)
            structured_res[k][gs] = np.full(l, None)
            gs_indices[k] = {exp: i for i, exp in enumerate(exps)}
    for sr in sql_result:
        gs_name = sr[-1].grid_square_name
        exp_name = sr[-2].exposure_name
        key = sr[0].key
        structured_res[key][gs_name][gs_indices[key][exp_name]] = sr[0].value
    return structured_res
