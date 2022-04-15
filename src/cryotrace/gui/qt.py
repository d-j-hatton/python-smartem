from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtGui import QBrush, QColor, QPainter, QPixmap, QTransform
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import cryotrace.gui
from cryotrace.data_model import Exposure, FoilHole, GridSquare
from cryotrace.data_model.extract import Extractor
from cryotrace.parsing.epu import create_atlas_and_tiles, parse_epu_dir
from cryotrace.stage_model import find_point_pixel


class App:
    def __init__(self, extractor: Extractor):
        self.app = QApplication([])
        self.window = QtFrame(extractor)
        self.app.setStyleSheet(
            importlib.resources.read_text(cryotrace.gui, "qt_style.css")
        )

    def start(self):
        self.window.show()
        self.app.exec()


class QtFrame(QWidget):
    def __init__(self, extractor: Extractor):
        super().__init__()
        self.tabs = QTabWidget()
        self.layout = QVBoxLayout(self)
        main_display = MainDisplay(extractor)
        proj_loader = ProjectLoader(extractor, main_display)
        self.tabs.addTab(proj_loader, "Project")
        self.tabs.addTab(main_display, "Grid square view")
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ProjectLoader(QWidget):
    def __init__(self, extractor: Extractor, main_display: MainDisplay):
        super().__init__()
        self._extractor = extractor
        self._main_display = main_display
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self.epu_dir = ""
        self._combo = QComboBox()
        atlases = self._extractor.get_atlases()
        for atl in atlases:
            self._combo.addItem(atl)
        self._combo.currentIndexChanged.connect(self._select_atlas_combo)
        self.grid.addWidget(self._combo, 1, 1)
        self.atlas = self._combo.currentText()
        epu_btn = QPushButton("Select EPU directory")
        epu_btn.clicked.connect(self._select_epu_dir)
        self.grid.addWidget(epu_btn, 2, 1)
        self.epu_lbl = QLabel()
        self.epu_lbl.setText(f"Selected: {self.epu_dir}")
        self.grid.addWidget(self.epu_lbl, 2, 3)
        atlas_btn = QPushButton("Select Atlas")
        atlas_btn.clicked.connect(self._select_atlas)
        self.grid.addWidget(atlas_btn, 3, 1)
        self.atlas_lbl = QLabel()
        self.atlas_lbl.setText(f"Selected: {self.atlas}")
        self.grid.addWidget(self.atlas_lbl, 3, 3)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load)
        self.grid.addWidget(load_btn, 4, 2)

    def _select_epu_dir(self):
        self.epu_dir = QFileDialog.getExistingDirectory(
            self, "Select EPU directory", ".", QFileDialog.ShowDirsOnly
        )
        self.epu_lbl.setText(f"Selected: {self.epu_dir}")

    def _select_atlas_combo(self, index: int):
        self.atlas = self._combo.currentText()
        self.atlas_lbl.setText(f"Selected: {self.atlas}")

    def _select_atlas(self):
        self.atlas = QFileDialog.getOpenFileName(self, "Select Atlas image", ".")[0]
        self.atlas_lbl.setText(f"Selected: {self.atlas}")

    def load(self):
        atlas_found = self._extractor.set_atlas_id(self.atlas)
        if atlas_found:
            self._main_display.load()
            return
        create_atlas_and_tiles(Path(self.atlas), self._extractor)
        atlas_found = self._extractor.set_atlas_id(self.atlas)
        if not atlas_found:
            raise ValueError("Atlas record not found despite having just been inserted")
        parse_epu_dir(Path(self.epu_dir), self._extractor)
        self._main_display.load()


class MainDisplay(QWidget):
    def __init__(self, extractor: Extractor):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._square_combo = QComboBox()
        self._square_combo.currentIndexChanged.connect(self._select_square)
        self._foil_hole_combo = QComboBox()
        self._foil_hole_combo.currentIndexChanged.connect(self._select_foil_hole)
        self._exposure_combo = QComboBox()
        self._exposure_combo.currentIndexChanged.connect(self._select_exposure)
        self.grid.addWidget(self._square_combo, 1, 1)
        self.grid.addWidget(self._foil_hole_combo, 1, 2)
        self.grid.addWidget(self._exposure_combo, 1, 3)
        self._grid_squares: List[GridSquare] = []
        self._foil_holes: List[FoilHole] = []
        self._exposures: List[Exposure] = []

    def load(self):
        self._grid_squares = self._extractor.get_grid_squares()
        self._square_combo.clear()
        for gs in self._grid_squares:
            self._square_combo.addItem(gs.grid_square_name)
        self._update_fh_choices(self._grid_squares[0].grid_square_name)

    def _select_square(self, index: int):
        square_lbl = QLabel(self)
        square_pixmap = QPixmap(self._grid_squares[index].thumbnail)
        square_lbl.setPixmap(square_pixmap)
        self.grid.addWidget(square_lbl, 2, 1)
        self._update_fh_choices(self._square_combo.currentText())

    def _select_foil_hole(self, index: int):
        hole_lbl = self._draw_foil_hole(self._foil_holes[index], flip=(-1, -1))
        self.grid.addWidget(hole_lbl, 2, 2)
        self._update_exposure_choices(self._foil_hole_combo.currentText())

    def _draw_foil_hole(
        self,
        foil_hole: FoilHole,
        exposure: Optional[Exposure] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> QLabel:
        print("drawing foil hole image")
        hole_lbl = QLabel(self)
        hole_pixmap = QPixmap(foil_hole.thumbnail)
        foil_hole_qtsize = hole_pixmap.size()
        foil_hole_size = (foil_hole_qtsize.width(), foil_hole_qtsize.height())
        if flip != (1, 1):
            hole_pixmap = hole_pixmap.transformed(QTransform().scale(*flip))
        if exposure:
            painter = QPainter(hole_pixmap)
            painter.setBrush(QBrush(QColor("green")))
            scaled_fh_pixel_size = foil_hole.pixel_size * (
                foil_hole.readout_area_x / foil_hole_size[0]
            )
            rect_centre = find_point_pixel(
                (exposure.stage_position_x, exposure.stage_position_y),
                (foil_hole.stage_position_x, foil_hole.stage_position_y),
                scaled_fh_pixel_size,
                (foil_hole.readout_area_x, foil_hole.readout_area_y),
                xfactor=-1,
                yfactor=-1,
            )
            edge_lengths = (
                int(
                    exposure.readout_area_x * exposure.pixel_size / scaled_fh_pixel_size
                ),
                int(
                    exposure.readout_area_y * exposure.pixel_size / scaled_fh_pixel_size
                ),
            )
            painter.drawRect(
                rect_centre[0] - 0.5 * edge_lengths[0],
                rect_centre[1] - 0.5 * edge_lengths[1],
                edge_lengths[0],
                edge_lengths[1],
            )
            painter.end()
        hole_lbl.setPixmap(hole_pixmap)
        return hole_lbl

    def _select_exposure(self, index: int):
        exposure_lbl = QLabel(self)
        exposure_pixmap = QPixmap(self._exposures[index].thumbnail)
        exposure_lbl.setPixmap(exposure_pixmap)
        self.grid.addWidget(exposure_lbl, 2, 3)
        self._draw_foil_hole(
            self._foil_holes[self._foil_hole_combo.currentIndex()],
            exposure=self._exposures[index],
        )

    def _update_fh_choices(self, grid_square_name: str):
        self._foil_holes = self._extractor.get_foil_holes(grid_square_name)
        self._foil_hole_combo.clear()
        for fh in self._foil_holes:
            self._foil_hole_combo.addItem(fh.foil_hole_name)

    def _update_exposure_choices(self, foil_hole_name: str):
        self._exposures = self._extractor.get_exposures(foil_hole_name)
        self._exposure_combo.clear()
        for ex in self._exposures:
            self._exposure_combo.addItem(ex.exposure_name)
