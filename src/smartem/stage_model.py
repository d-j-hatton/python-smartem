from typing import NamedTuple, Tuple

import numpy as np


def find_point_pixel(
    inner_pos: Tuple[float, float],
    outer_centre: Tuple[float, float],
    outer_spacing: float,
    outer_size: Tuple[int, int],
    xfactor: int = 1,
    yfactor: int = 1,
) -> Tuple[int, int]:
    delta = (
        (outer_centre[0] - inner_pos[0]) / outer_spacing,
        (outer_centre[1] - inner_pos[1]) / outer_spacing,
    )
    outer_centre_pix = (outer_size[0] // 2, outer_size[1] // 2)
    return (
        outer_centre_pix[0] + xfactor * int(delta[0]),
        outer_centre_pix[1] + yfactor * int(delta[1]),
    )


def stage_position(
    pix_pos: Tuple[int, int],
    spacing: float,
    physical_centre: Tuple[float, float],
    image_size: Tuple[int, int],
) -> Tuple[float, float]:
    pix_centre = (image_size[0] // 2, image_size[1] // 2)
    delta = (
        -(pix_pos[0] - pix_centre[0]) * spacing,
        (pix_pos[1] - pix_centre[1]) * spacing,
    )
    return (physical_centre[0] + delta[0], physical_centre[1] + delta[1])


class StageCalibration(NamedTuple):
    inverted: bool = False
    x_flip: bool = False
    y_flip: bool = False


def calibrate(
    pix_positions: Tuple[Tuple[int, int], Tuple[int, int]],
    physical_positions: Tuple[Tuple[float, float], Tuple[float, float]],
) -> StageCalibration:
    pix_diff = (
        pix_positions[1][0] - pix_positions[0][0],
        pix_positions[1][1] - pix_positions[0][1],
    )
    physical_diff = (
        physical_positions[1][0] - physical_positions[0][0],
        physical_positions[1][1] - physical_positions[0][1],
    )
    inv_checks = (
        abs(
            1 - abs((pix_diff[0] / physical_diff[0]) / (pix_diff[1] / physical_diff[1]))
        ),
        abs(
            1 - abs((pix_diff[0] / physical_diff[1]) / (pix_diff[1] / physical_diff[0]))
        ),
    )
    inv = bool(np.argmin(inv_checks))
    if inv:
        if pix_diff[0] / physical_diff[1] > 0:
            x_flip = True
        else:
            x_flip = False
        if pix_diff[1] / physical_diff[0] > 0:
            y_flip = True
        else:
            y_flip = False
    else:
        if pix_diff[0] / physical_diff[0] > 0:
            x_flip = True
        else:
            x_flip = False
        if pix_diff[1] / physical_diff[1] > 0:
            y_flip = True
        else:
            y_flip = False
    return StageCalibration(inverted=inv, x_flip=x_flip, y_flip=y_flip)
