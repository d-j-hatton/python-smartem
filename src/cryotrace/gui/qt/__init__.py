from __future__ import annotations

import importlib.resources

import matplotlib

matplotlib.use("Qt5Agg")
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtGui import QPixmap, QTransform
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
from cryotrace.gui.qt.image_utils import ImageLabel, ParticleImageLabel
from cryotrace.gui.qt.loader import (
    ExposureDataLoader,
    ParticleDataLoader,
    ParticleSetDataLoader,
)
from cryotrace.parsing.epu import create_atlas_and_tiles, parse_epu_dir


class App:
    def __init__(self, extractor: Extractor):
        self.app = QApplication([])
        self.window = QtFrame(extractor)
        self.app.setStyleSheet(
            importlib.resources.read_text(cryotrace.gui.qt, "qt_style.css")
        )

    def start(self):
        self.window.show()
        self.app.exec()


class QtFrame(QWidget):
    def __init__(self, extractor: Extractor):
        super().__init__()
        self.tabs = QTabWidget()
        self.layout = QVBoxLayout(self)
        atlas_display = AtlasDisplay(extractor)
        main_display = MainDisplay(extractor, atlas_view=atlas_display)
        data_loader = ExposureDataLoader(extractor)
        particle_loader = ParticleDataLoader(extractor)
        particle_set_loader = ParticleSetDataLoader(extractor)
        proj_loader = ProjectLoader(
            extractor,
            data_loader,
            particle_loader,
            particle_set_loader,
            main_display,
            atlas_display,
        )
        self.tabs.addTab(proj_loader, "Project")
        self.tabs.addTab(data_loader, "Load mic data")
        self.tabs.addTab(particle_loader, "Load particle data")
        self.tabs.addTab(particle_set_loader, "Load particle set data")
        self.tabs.addTab(main_display, "Grid square view")
        self.tabs.addTab(atlas_display, "Atlas view")
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ProjectLoader(QWidget):
    def __init__(
        self,
        extractor: Extractor,
        data_loader: ExposureDataLoader,
        particle_loader: ParticleDataLoader,
        particle_set_loader: ParticleSetDataLoader,
        main_display: MainDisplay,
        atlas_display: AtlasDisplay,
    ):
        super().__init__()
        self._extractor = extractor
        self._data_loader = data_loader
        self._particle_loader = particle_loader
        self._particle_set_loader = particle_set_loader
        self._main_display = main_display
        self._atlas_display = atlas_display
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self.epu_dir = ""
        self.project_dir = ""
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
        project_btn = QPushButton("Select project directory")
        project_btn.clicked.connect(self._select_project)
        self.grid.addWidget(project_btn, 4, 1)
        self.project_lbl = QLabel()
        self.project_lbl.setText(f"Selected: {self.project_dir}")
        self.grid.addWidget(self.project_lbl, 4, 3)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load)
        self.grid.addWidget(load_btn, 5, 2)

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

    def _select_project(self):
        self.project_dir = QFileDialog.getExistingDirectory(
            self, "Select project directory", ".", QFileDialog.ShowDirsOnly
        )
        self.project_lbl.setText(f"Selected: {self.project_dir}")
        self._data_loader._set_project_directory(Path(self.project_dir))
        self._particle_loader._set_project_directory(Path(self.project_dir))
        self._particle_set_loader._set_project_directory(Path(self.project_dir))

    def load(self):
        atlas_found = self._extractor.set_atlas_id(self.atlas)
        if atlas_found:
            self._main_display.load()
            self._atlas_display.load()
            return
        create_atlas_and_tiles(Path(self.atlas), self._extractor)
        atlas_found = self._extractor.set_atlas_id(self.atlas)
        if not atlas_found:
            raise ValueError("Atlas record not found despite having just been inserted")
        parse_epu_dir(Path(self.epu_dir), self._extractor)
        self._main_display.load()
        self._atlas_display.load()


class MainDisplay(QWidget):
    def __init__(self, extractor: Extractor, atlas_view: Optional[AtlasDisplay] = None):
        super().__init__()
        self._extractor = extractor
        self._data: Dict[str, List[float]] = {}
        self._particle_data: Dict[str, List[float]] = {}
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._square_combo = QComboBox()
        self._square_combo.currentIndexChanged.connect(self._select_square)
        self._foil_hole_combo = QComboBox()
        self._foil_hole_combo.currentIndexChanged.connect(self._select_foil_hole)
        self._exposure_combo = QComboBox()
        self._exposure_combo.currentIndexChanged.connect(self._select_exposure)
        self._data_combo = QComboBox()
        self._particle_data_combo = QComboBox()
        fh_fig = Figure()
        self._foil_hole_stats_fig = fh_fig.add_subplot(111)
        self._foil_hole_stats = FigureCanvasQTAgg(fh_fig)
        gs_fig = Figure()
        self._grid_square_stats_fig = gs_fig.add_subplot(111)
        self._grid_square_stats = FigureCanvasQTAgg(gs_fig)
        ex_fig = Figure()
        self._exposure_stats_fig = ex_fig.add_subplot(111)
        self._exposure_stats = FigureCanvasQTAgg(ex_fig)
        fhp_fig = Figure()
        self._foil_hole_stats_particle_fig = fhp_fig.add_subplot(111)
        self._foil_hole_stats_particle = FigureCanvasQTAgg(fhp_fig)
        gsp_fig = Figure()
        self._grid_square_stats_particle_fig = gsp_fig.add_subplot(111)
        self._grid_square_stats_particle = FigureCanvasQTAgg(gsp_fig)
        self.grid.addWidget(self._square_combo, 2, 1)
        self.grid.addWidget(self._foil_hole_combo, 2, 2)
        self.grid.addWidget(self._exposure_combo, 2, 3)
        self.grid.addWidget(self._data_combo, 3, 2)
        self.grid.addWidget(self._particle_data_combo, 3, 3)
        self.grid.addWidget(self._grid_square_stats, 4, 1)
        self.grid.addWidget(self._grid_square_stats_particle, 5, 1)
        self.grid.addWidget(self._foil_hole_stats, 4, 2)
        self.grid.addWidget(self._foil_hole_stats_particle, 5, 2)
        self.grid.addWidget(self._exposure_stats, 5, 3)
        self._grid_squares: List[GridSquare] = []
        self._foil_holes: List[FoilHole] = []
        self._exposures: List[Exposure] = []
        self._atlas_view = atlas_view

    def load(self):
        self._grid_squares = self._extractor.get_grid_squares()
        self._square_combo.clear()
        for gs in self._grid_squares:
            self._square_combo.addItem(gs.grid_square_name)
        self._update_fh_choices(self._grid_squares[0].grid_square_name)
        self._data_combo.clear()
        self._particle_data_combo.clear()
        data_keys = self._extractor.get_all_exposure_keys()
        for k in data_keys:
            self._data_combo.addItem(k)
        p_data_keys = self._extractor.get_all_particle_keys()
        p_data_keys.extend(self._extractor.get_all_particle_set_keys())
        for k in p_data_keys:
            self._particle_data_combo.addItem(k)

    def _select_square(self, index: int):
        try:
            square_lbl = self._draw_grid_square(self._grid_squares[index])
        except IndexError:
            return
        self.grid.addWidget(square_lbl, 1, 1)
        self._update_fh_choices(self._square_combo.currentText())
        p_keys = self._extractor.get_all_particle_keys()
        ps_keys = self._extractor.get_all_particle_set_keys()
        if self._atlas_view:
            self._atlas_view.load(
                grid_square=self._grid_squares[index],
                all_grid_squares=self._grid_squares,
                data_key=self._data_combo.currentText() or None,
                particle_data_key=self._particle_data_combo.currentText()
                if self._particle_data_combo.currentText() in p_keys
                else None,
                particle_set_data_key=self._particle_data_combo.currentText()
                if self._particle_data_combo.currentText() in ps_keys
                else None,
            )
        self._data = self._extractor.get_grid_square_stats(
            self._square_combo.currentText(), self._data_combo.currentText()
        )
        self._update_grid_square_stats(
            [elem for foil_hole in self._data.values() for elem in foil_hole]
        )
        if self._particle_data_combo.currentText() in p_keys:
            self._particle_data = self._extractor.get_grid_square_stats_particle(
                self._square_combo.currentText(),
                self._particle_data_combo.currentText(),
            )
        elif self._particle_data_combo.currentText() in ps_keys:
            self._particle_data = self._extractor.get_grid_square_stats_particle_set(
                self._square_combo.currentText(),
                self._particle_data_combo.currentText(),
            )
        self._update_grid_square_stats_particle(
            [elem for foil_hole in self._particle_data.values() for elem in foil_hole]
        )

    def _select_foil_hole(self, index: int):
        try:
            hole_lbl = self._draw_foil_hole(self._foil_holes[index], flip=(-1, -1))
        except IndexError:
            return
        self.grid.addWidget(hole_lbl, 1, 2)
        self._update_exposure_choices(self._foil_hole_combo.currentText())
        self._draw_grid_square(
            self._grid_squares[self._square_combo.currentIndex()],
            foil_hole=self._foil_holes[index],
        )
        if self._data and self._foil_hole_combo.currentText():
            try:
                self._update_foil_hole_stats(
                    self._data[self._foil_hole_combo.currentText()]
                )
            except KeyError:
                pass
        if self._particle_data and self._foil_hole_combo.currentText():
            try:
                self._update_foil_hole_stats_particle(
                    self._particle_data[self._foil_hole_combo.currentText()]
                )
            except KeyError:
                pass

    def _update_grid_square_stats(self, stats: List[float]):
        self._grid_square_stats_fig.cla()
        self._grid_square_stats_fig.hist(stats)
        self._grid_square_stats.draw()

    def _update_grid_square_stats_particle(self, stats: List[float]):
        self._grid_square_stats_particle_fig.cla()
        self._grid_square_stats_particle_fig.hist(stats)
        self._grid_square_stats_particle.draw()

    def _update_foil_hole_stats(self, stats: List[float]):
        self._foil_hole_stats_fig.cla()
        self._foil_hole_stats_fig.hist(stats)
        self._foil_hole_stats.draw()

    def _update_foil_hole_stats_particle(self, stats: List[float]):
        self._foil_hole_stats_particle_fig.cla()
        self._foil_hole_stats_particle_fig.hist(stats)
        self._foil_hole_stats_particle.draw()

    def _update_exposure_stats(self, stats: List[float]):
        self._exposure_stats_fig.cla()
        self._exposure_stats_fig.hist(stats)
        self._exposure_stats.draw()

    def _draw_grid_square(
        self,
        grid_square: GridSquare,
        foil_hole: Optional[FoilHole] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> QLabel:
        square_pixmap = QPixmap(grid_square.thumbnail)
        if flip != (1, 1):
            square_pixmap = square_pixmap.transformed(QTransform().scale(*flip))
        if foil_hole:
            qsize = square_pixmap.size()
            imvs: Optional[list] = None
            if self._data:
                imvs = [
                    np.mean(self._data.get(fh.foil_hole_name, []))
                    for fh in self._foil_holes
                    if fh != foil_hole
                ]
                imvs = list(np.nan_to_num(imvs))
            square_lbl = ImageLabel(
                grid_square,
                foil_hole,
                (qsize.width(), qsize.height()),
                parent=self,
                value=np.mean(self._data.get(foil_hole.foil_hole_name, [0])),
                extra_images=[fh for fh in self._foil_holes if fh != foil_hole],
                image_values=imvs,
            )
            self.grid.addWidget(square_lbl, 1, 1)
            square_lbl.setPixmap(square_pixmap)
        else:
            square_lbl = QLabel(self)
            square_lbl.setPixmap(square_pixmap)
        return square_lbl

    def _draw_foil_hole(
        self,
        foil_hole: FoilHole,
        exposure: Optional[Exposure] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> QLabel:
        hole_pixmap = QPixmap(foil_hole.thumbnail)
        if flip != (1, 1):
            hole_pixmap = hole_pixmap.transformed(QTransform().scale(*flip))
        if exposure:
            qsize = hole_pixmap.size()
            hole_lbl = ImageLabel(
                foil_hole,
                exposure,
                (qsize.width(), qsize.height()),
                parent=self,
            )
            self.grid.addWidget(hole_lbl, 1, 2)
            hole_lbl.setPixmap(hole_pixmap)
        else:
            hole_lbl = QLabel(self)
            hole_lbl.setPixmap(hole_pixmap)
        return hole_lbl

    def _select_exposure(self, index: int):
        exposure_lbl = QLabel(self)
        try:
            exposure_lbl = self._draw_exposure(self._exposures[index], flip=(1, -1))
        except IndexError:
            return
        self.grid.addWidget(exposure_lbl, 1, 3)
        self._draw_foil_hole(
            self._foil_holes[self._foil_hole_combo.currentIndex()],
            exposure=self._exposures[index],
            flip=(-1, -1),
        )
        p_keys = self._extractor.get_all_particle_keys()
        ps_keys = self._extractor.get_all_particle_set_keys()
        particle_stats = []
        if self._particle_data_combo.currentText() in p_keys:
            particle_stats = self._extractor.get_exposure_stats(
                self._exposures[index].exposure_name,
                self._particle_data_combo.currentText(),
            )
        elif self._particle_data_combo.currentText() in ps_keys:
            particle_stats = self._extractor.get_exposure_stats_particle_set(
                self._exposures[index].exposure_name,
                self._particle_data_combo.currentText(),
            )
        self._update_exposure_stats(particle_stats)

    def _draw_exposure(
        self, exposure: Exposure, flip: Tuple[int, int] = (1, 1)
    ) -> QLabel:
        exposure_pixmap = QPixmap(exposure.thumbnail)
        if flip != (1, 1):
            exposure_pixmap = exposure_pixmap.transformed(QTransform().scale(*flip))
        qsize = exposure_pixmap.size()
        particles = self._extractor.get_particles(exposure.exposure_name)
        exposure_lbl = ParticleImageLabel(
            exposure, particles, (qsize.width(), qsize.height())
        )
        self.grid.addWidget(exposure_lbl, 1, 3)
        exposure_lbl.setPixmap(exposure_pixmap)
        return exposure_lbl

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


class AtlasDisplay(QWidget):
    def __init__(self, extractor: Extractor):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        atlas_fig = Figure()
        self._atlas_stats_fig = atlas_fig.add_subplot(111)
        self._atlas_stats = FigureCanvasQTAgg(atlas_fig)
        atlas_particle_fig = Figure()
        self._atlas_stats_particle_fig = atlas_particle_fig.add_subplot(111)
        self._atlas_stats_particle = FigureCanvasQTAgg(atlas_particle_fig)
        self.grid.addWidget(self._atlas_stats, 2, 1)
        self.grid.addWidget(self._atlas_stats_particle, 3, 1)
        self._data: Dict[str, List[float]] = {}
        self._particle_data: Dict[str, List[float]] = {}

    def load(
        self,
        grid_square: Optional[GridSquare] = None,
        all_grid_squares: Optional[List[GridSquare]] = None,
        data_key: Optional[str] = None,
        particle_data_key: Optional[str] = None,
        particle_set_data_key: Optional[str] = None,
    ):
        if data_key:
            self._data = self._extractor.get_atlas_stats(data_key)
            self._update_atlas_stats()
        if particle_data_key:
            self._particle_data = self._extractor.get_atlas_stats_particle(
                particle_data_key
            )
            self._update_atlas_stats_particle()
        if particle_set_data_key:
            self._particle_data = self._extractor.get_atlas_stats_particle_set(
                particle_set_data_key
            )
            self._update_atlas_stats_particle()
        atlas_lbl = self._draw_atlas(
            grid_square=grid_square, all_grid_squares=all_grid_squares
        )
        if atlas_lbl:
            self.grid.addWidget(atlas_lbl, 1, 1)
        if grid_square:
            tile_lbl = self._draw_tile(grid_square)
            self.grid.addWidget(tile_lbl, 1, 2)

    def _update_atlas_stats(self):
        stats = []
        for d in self._data.values():
            stats.extend(d)
        self._atlas_stats_fig.cla()
        self._atlas_stats_fig.hist(stats)
        self._atlas_stats.draw()

    def _update_atlas_stats_particle(self):
        stats = []
        for d in self._particle_data.values():
            stats.extend(d)
        self._atlas_stats_particle_fig.cla()
        self._atlas_stats_particle_fig.hist(stats)
        self._atlas_stats_particle.draw()

    def _draw_atlas(
        self,
        grid_square: Optional[GridSquare] = None,
        all_grid_squares: Optional[List[GridSquare]] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> Optional[QLabel]:
        _atlas = self._extractor.get_atlas()
        if _atlas:
            atlas_pixmap = QPixmap(_atlas.thumbnail)
            if flip != (1, 1):
                atlas_pixmap = atlas_pixmap.transformed(QTransform().scale(*flip))
            if grid_square:
                imvs: Optional[list] = None
                if self._data and grid_square and all_grid_squares:
                    imvs = [
                        np.mean(self._data.get(gs.grid_square_name, []))
                        for gs in all_grid_squares
                        if gs != grid_square
                    ]
                    imvs = list(np.nan_to_num(imvs))
                qsize = atlas_pixmap.size()
                atlas_lbl = ImageLabel(
                    _atlas,
                    grid_square,
                    (qsize.width(), qsize.height()),
                    parent=self,
                    overwrite_readout=True,
                    value=np.mean(self._data.get(grid_square.grid_square_name, [0])),
                    extra_images=[gs for gs in all_grid_squares if gs != grid_square]
                    if all_grid_squares
                    else [],
                    image_values=imvs,
                )
                self.grid.addWidget(atlas_lbl, 1, 1)
                atlas_lbl.setPixmap(atlas_pixmap)
            else:
                atlas_lbl = QLabel(self)
                atlas_lbl.setPixmap(atlas_pixmap)
            return atlas_lbl
        return None

    def _draw_tile(
        self, grid_square: GridSquare, flip: Tuple[int, int] = (1, 1)
    ) -> Optional[QLabel]:
        _tile = self._extractor.get_tile(
            (grid_square.stage_position_x, grid_square.stage_position_y)
        )
        if _tile:
            tile_pixmap = QPixmap(_tile.thumbnail)
            if flip != (1, 1):
                tile_pixmap = tile_pixmap.transformed(QTransform().scale(*flip))
            qsize = tile_pixmap.size()
            tile_lbl = ImageLabel(
                _tile, grid_square, (qsize.width(), qsize.height()), parent=self
            )
            self.grid.addWidget(tile_lbl, 1, 1)
            tile_lbl.setPixmap(tile_pixmap)
            return tile_lbl
        return None
