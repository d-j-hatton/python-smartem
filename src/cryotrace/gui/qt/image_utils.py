from typing import List, Optional, Tuple, Union

import matplotlib
import mrcfile
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen
from PyQt5.QtWidgets import QLabel

from cryotrace.data_model import Atlas, Exposure, FoilHole, GridSquare, Particle, Tile
from cryotrace.stage_model import find_point_pixel


def colour_gradient(value: float) -> str:
    low = "#EF3054"
    high = "#47682C"
    low_rgb = np.array(matplotlib.colors.to_rgb(low))
    high_rgb = np.array(matplotlib.colors.to_rgb(high))
    return matplotlib.colors.to_hex((1 - value) * low_rgb + value * high_rgb)


class ParticleImageLabel(QLabel):
    def __init__(
        self,
        image: Exposure,
        particles: List[Particle],
        image_size: Tuple[int, int],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._image = image
        self._image_size = image_size
        self._particles = particles

    def draw_circle(
        self, coordinates: Tuple[float, float], diameter: int, painter: QPainter
    ):
        x = (
            coordinates[0] * 0.5 * (self._image_size[0] / self._image.readout_area_x)
            - diameter / 2
        )
        y = (
            coordinates[1] * 0.5 * (self._image_size[1] / self._image.readout_area_y)
            - diameter / 2
        )
        painter.drawEllipse(x, y, diameter, diameter)

    def paintEvent(self, e):
        super().paintEvent(e)

        painter = QPainter(self)
        pen = QPen(QColor(QtCore.Qt.blue))
        pen.setWidth(3)
        painter.setPen(pen)

        for particle in self._particles:
            self.draw_circle((particle.x, particle.y), 30, painter)

        painter.end()


class ImageLabel(QLabel):
    def __init__(
        self,
        image: Union[Atlas, Tile, GridSquare, FoilHole, Exposure],
        contained_image: Optional[Union[GridSquare, FoilHole, Exposure]],
        image_size: Tuple[int, int],
        overwrite_readout: bool = False,
        value: Optional[float] = None,
        extra_images: Optional[list] = None,
        image_values: Optional[List[float]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._image = image
        self._contained_image = contained_image
        self._extra_images = extra_images or []
        self._image_size = image_size
        self._overwrite_readout = overwrite_readout
        self._value = value
        self._image_values = image_values or []

    def draw_rectangle(
        self,
        inner_image: Union[GridSquare, FoilHole, Exposure],
        readout_area: Tuple[int, int],
        scaled_pixel_size: float,
        painter: QPainter,
        normalised_value: Optional[float] = None,
    ):
        if normalised_value is not None:
            c = QColor()
            rgb = (
                int(255 * x)
                for x in matplotlib.colors.to_rgb(colour_gradient(normalised_value))
            )
            c.setRgb(*rgb, alpha=150)
            brush = QBrush(c, QtCore.Qt.SolidPattern)
            painter.setBrush(brush)
        else:
            brush = QBrush()
            painter.setBrush(brush)
        rect_centre = find_point_pixel(
            (
                inner_image.stage_position_x,
                inner_image.stage_position_y,
            ),
            (self._image.stage_position_x, self._image.stage_position_y),
            scaled_pixel_size,
            (
                int(readout_area[0] / (scaled_pixel_size / self._image.pixel_size)),
                int(readout_area[1] / (scaled_pixel_size / self._image.pixel_size)),
            ),
            xfactor=1,
            yfactor=-1,
        )
        edge_lengths = (
            int(
                inner_image.readout_area_x * inner_image.pixel_size / scaled_pixel_size
            ),
            int(
                inner_image.readout_area_y * inner_image.pixel_size / scaled_pixel_size
            ),
        )
        painter.drawRect(
            int(rect_centre[0] - 0.5 * edge_lengths[0]),
            int(rect_centre[1] - 0.5 * edge_lengths[1]),
            edge_lengths[0],
            edge_lengths[1],
        )

    def paintEvent(self, e):
        super().paintEvent(e)

        if self._contained_image:
            painter = QPainter(self)
            pen = QPen(QColor(QtCore.Qt.blue))
            pen.setWidth(3)
            painter.setPen(pen)
            if self._overwrite_readout:
                with mrcfile.open(self._image.thumbnail.replace(".jpg", ".mrc")) as mrc:
                    readout_area = mrc.data.shape
            else:
                readout_area = (self._image.readout_area_x, self._image.readout_area_y)
            scaled_pixel_size = self._image.pixel_size * (
                readout_area[0] / self._image_size[0]
            )

            if self._image_values:
                shifted = [
                    iv - min(self._image_values + [self._value])
                    for iv in self._image_values
                ]
                maxv = max(self._image_values + [self._value])
                if maxv:
                    normalised = [s / maxv for s in shifted]
                else:
                    normalised = shifted
            for i, im in enumerate(self._extra_images):
                if self._image_values:
                    self.draw_rectangle(
                        im,
                        readout_area,
                        scaled_pixel_size,
                        painter,
                        normalised_value=normalised[i],
                    )
                else:
                    self.draw_rectangle(im, readout_area, scaled_pixel_size, painter)

            pen = QPen(QColor(QtCore.Qt.red))
            pen.setWidth(3)
            painter.setPen(pen)

            if self._value:
                norm_value = (
                    self._value - min(self._image_values + [self._value])
                ) / max(self._image_values + [self._value])
            else:
                norm_value = 0

            norm_value = np.nan_to_num(norm_value)

            if self._value is not None:
                self.draw_rectangle(
                    self._contained_image,
                    readout_area,
                    scaled_pixel_size,
                    painter,
                    normalised_value=norm_value,
                )
            else:
                self.draw_rectangle(
                    self._contained_image, readout_area, scaled_pixel_size, painter
                )

            painter.end()