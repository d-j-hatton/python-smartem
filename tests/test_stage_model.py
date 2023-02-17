from smartem import stage_model


def test_find_point_pixel():
    return_value = stage_model.find_point_pixel(
        inner_pos=(0.5, 1.5),
        outer_centre=(2.5, 5.5),
        outer_spacing=4,
        outer_size=(1, 2),
        xfactor=1,
        yfactor=1,
    )

    assert return_value == (0.0, 2.0)


def test_stage_position():
    return_value = stage_model.stage_position(
        pix_pos=(2, 3), spacing=0.5, physical_centre=(1.5, 2.5), image_size=(3, 4)
    )

    assert return_value == (1.0, 3.0)


def test_calibrate():
    """Calibration when not inverted or flipped"""
    return_value = stage_model.calibrate(
        pix_positions=((0, 0), (-1, -1)), physical_positions=((0, 0), (1, 1))
    )

    assert type(return_value) == stage_model.StageCalibration
    assert not return_value.inverted
    assert not return_value.x_flip
    assert not return_value.y_flip


def test_calibrate_inv():
    """Calibration when inverted"""
    return_value = stage_model.calibrate(
        pix_positions=((0, 0), (-2, -1)), physical_positions=((0, 0), (0.5, 1))
    )

    assert type(return_value) == stage_model.StageCalibration
    assert return_value.inverted
    assert not return_value.x_flip
    assert not return_value.y_flip


def test_calibrate_flip():
    """Calibration when flipped"""
    return_value = stage_model.calibrate(
        pix_positions=((0, 0), (1, 1)), physical_positions=((0, 0), (1, 1))
    )

    assert type(return_value) == stage_model.StageCalibration
    assert not return_value.inverted
    assert return_value.x_flip
    assert return_value.y_flip


def test_calibrate_inv_flip():
    """Calibration when inverted and flipped"""
    return_value = stage_model.calibrate(
        pix_positions=((0, 0), (2, 1)), physical_positions=((0, 0), (0.5, 1))
    )

    assert type(return_value) == stage_model.StageCalibration
    assert return_value.inverted
    assert return_value.x_flip
    assert return_value.y_flip
