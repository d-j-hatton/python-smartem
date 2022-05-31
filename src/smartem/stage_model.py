from typing import Tuple


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
