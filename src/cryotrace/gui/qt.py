from __future__ import annotations

import importlib.resources

import matplotlib

matplotlib.use("Qt5Agg")
from pathlib import Path
from typing import List, Optional, Tuple, Union

import mrcfile
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtCore
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap, QTransform
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
from cryotrace.data_model import Atlas, Exposure, FoilHole, GridSquare, Tile
from cryotrace.data_model.extract import Extractor
from cryotrace.parsing.epu import create_atlas_and_tiles, parse_epu_dir
from cryotrace.parsing.star import (
    get_column_data,
    get_columns,
    insert_exposure_data,
    open_star_file,
)
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
        atlas_display = AtlasDisplay(extractor)
        main_display = MainDisplay(extractor, atlas_view=atlas_display)
        data_loader = DataLoader(extractor)
        proj_loader = ProjectLoader(extractor, data_loader, main_display, atlas_display)
        self.tabs.addTab(proj_loader, "Project")
        self.tabs.addTab(data_loader, "Load data")
        self.tabs.addTab(main_display, "Grid square view")
        self.tabs.addTab(atlas_display, "Atlas view")
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ProjectLoader(QWidget):
    def __init__(
        self,
        extractor: Extractor,
        data_loader: DataLoader,
        main_display: MainDisplay,
        atlas_display: AtlasDisplay,
    ):
        super().__init__()
        self._extractor = extractor
        self._data_loader = data_loader
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
        self._data_loader.set_project_directory(Path(self.project_dir))

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


class DataLoader(QWidget):
    def __init__(self, extractor: Extractor, project_directory: Optional[Path] = None):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._exposure_tag = None
        self._column = None
        self._proj_dir = project_directory
        self._file_combo = QComboBox()
        self._file_combo.setEditable(True)
        self._file_combo.currentIndexChanged.connect(self._select_star_file)
        self.grid.addWidget(self._file_combo, 1, 1)
        self._column_combo = QComboBox()
        self._column_combo.setEditable(True)
        self._column_combo.currentIndexChanged.connect(self._select_column)
        self.grid.addWidget(self._column_combo, 2, 1)
        self._exposure_tag_combo = QComboBox()
        self._exposure_tag_combo.setEditable(True)
        self._exposure_tag_combo.currentIndexChanged.connect(self._select_exposure_tag)
        self.grid.addWidget(self._exposure_tag_combo, 3, 1)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load)
        self.grid.addWidget(load_btn, 4, 1)
        if self._proj_dir:
            for sf in self._proj_dir.glob("**/*.star"):
                self._file_combo.addItem(str(sf))

    def set_project_directory(self, project_directory: Path):
        self._proj_dir = project_directory
        for sf in self._proj_dir.glob("*/*/*.star"):
            str_sf = str(sf)
            if (
                all(p not in str_sf for p in ("gui", "pipeline", "Nodes"))
                and "job" not in sf.name
            ):
                self._file_combo.addItem(str_sf)

    def _select_star_file(self, index: int):
        star_file_path = Path(self._file_combo.currentText())
        star_file = open_star_file(star_file_path)
        columns = get_columns(star_file, ignore=["pipeline"])
        for c in columns:
            self._column_combo.addItem(c)
            self._exposure_tag_combo.addItem(c)

    def _select_exposure_tag(self, index: int):
        self._exposure_tag = self._exposure_tag_combo.currentText()

    def _select_column(self, index: int):
        self._column = self._column_combo.currentText()

    def load(self):
        if self._exposure_tag and self._column:
            star_file_path = Path(self._file_combo.currentText())
            star_file = open_star_file(star_file_path)
            column_data = get_column_data(
                star_file, [self._exposure_tag, self._column], "micrographs"
            )
            insert_exposure_data(
                column_data, self._exposure_tag, str(star_file_path), self._extractor
            )


class MainDisplay(QWidget):
    def __init__(self, extractor: Extractor, atlas_view: Optional[AtlasDisplay] = None):
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
        self._data_combo = QComboBox()
        fig = Figure()
        self._foil_hole_stats_fig = fig.add_subplot(111)
        self._foil_hole_stats = FigureCanvasQTAgg(fig)
        self.grid.addWidget(self._square_combo, 1, 1)
        self.grid.addWidget(self._foil_hole_combo, 1, 2)
        self.grid.addWidget(self._exposure_combo, 1, 3)
        self.grid.addWidget(self._data_combo, 3, 2)
        self.grid.addWidget(self._foil_hole_stats, 4, 2)
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
        data_keys = self._extractor.get_all_exposure_keys()
        for k in data_keys:
            self._data_combo.addItem(k)

    def _select_square(self, index: int):
        try:
            square_lbl = self._draw_grid_square(self._grid_squares[index])
        except IndexError:
            return
        self.grid.addWidget(square_lbl, 2, 1)
        self._update_fh_choices(self._square_combo.currentText())
        if self._atlas_view:
            self._atlas_view.load(grid_square=self._grid_squares[index])

    def _select_foil_hole(self, index: int):
        try:
            hole_lbl = self._draw_foil_hole(self._foil_holes[index], flip=(-1, -1))
        except IndexError:
            return
        self.grid.addWidget(hole_lbl, 2, 2)
        self._update_exposure_choices(self._foil_hole_combo.currentText())
        self._draw_grid_square(
            self._grid_squares[self._square_combo.currentIndex()],
            foil_hole=self._foil_holes[index],
        )
        self._update_foil_hole_stats(
            self._extractor.get_foil_hole_stats(
                self._foil_hole_combo.currentText(), self._data_combo.currentText()
            )
        )

    def _update_foil_hole_stats(self, stats: List[float]):
        self._foil_hole_stats_fig.cla()
        self._foil_hole_stats_fig.hist(stats)
        self._foil_hole_stats.draw()

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
            square_lbl = ImageLabel(
                grid_square, foil_hole, (qsize.width(), qsize.height()), parent=self
            )
            self.grid.addWidget(square_lbl, 2, 1)
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
                foil_hole, exposure, (qsize.width(), qsize.height()), parent=self
            )
            self.grid.addWidget(hole_lbl, 2, 2)
            hole_lbl.setPixmap(hole_pixmap)
        else:
            hole_lbl = QLabel(self)
            hole_lbl.setPixmap(hole_pixmap)
        return hole_lbl

    def _select_exposure(self, index: int):
        exposure_lbl = QLabel(self)
        try:
            exposure_pixmap = QPixmap(self._exposures[index].thumbnail)
        except IndexError:
            return
        exposure_lbl.setPixmap(exposure_pixmap)
        self.grid.addWidget(exposure_lbl, 2, 3)
        self._draw_foil_hole(
            self._foil_holes[self._foil_hole_combo.currentIndex()],
            exposure=self._exposures[index],
            flip=(-1, -1),
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


class AtlasDisplay(QWidget):
    def __init__(self, extractor: Extractor):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        # self._draw_atlas()

    def load(self, grid_square: Optional[GridSquare] = None):
        atlas_lbl = self._draw_atlas(grid_square=grid_square)
        if atlas_lbl:
            self.grid.addWidget(atlas_lbl, 1, 1)
        if grid_square:
            tile_lbl = self._draw_tile(grid_square)
            self.grid.addWidget(tile_lbl, 1, 2)

    def _draw_atlas(
        self, grid_square: Optional[GridSquare] = None, flip: Tuple[int, int] = (1, 1)
    ) -> Optional[QLabel]:
        _atlas = self._extractor.get_atlas()
        if _atlas:
            atlas_pixmap = QPixmap(_atlas.thumbnail)
            if flip != (1, 1):
                atlas_pixmap = atlas_pixmap.transformed(QTransform().scale(*flip))
            if grid_square:
                qsize = atlas_pixmap.size()
                atlas_lbl = ImageLabel(
                    _atlas,
                    grid_square,
                    (qsize.width(), qsize.height()),
                    parent=self,
                    overwrite_readout=True,
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


class ImageLabel(QLabel):
    def __init__(
        self,
        image: Union[Atlas, Tile, GridSquare, FoilHole, Exposure],
        contained_image: Optional[Union[GridSquare, FoilHole, Exposure]],
        image_size: Tuple[int, int],
        overwrite_readout: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._image = image
        self._contained_image = contained_image
        self._image_size = image_size
        self._overwrite_readout = overwrite_readout

    def paintEvent(self, e):
        super().paintEvent(e)

        if self._contained_image:
            painter = QPainter(self)
            pen = QPen(QColor(QtCore.Qt.red))
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
            rect_centre = find_point_pixel(
                (
                    self._contained_image.stage_position_x,
                    self._contained_image.stage_position_y,
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
                    self._contained_image.readout_area_x
                    * self._contained_image.pixel_size
                    / scaled_pixel_size
                ),
                int(
                    self._contained_image.readout_area_y
                    * self._contained_image.pixel_size
                    / scaled_pixel_size
                ),
            )
            painter.drawRect(
                int(rect_centre[0] - 0.5 * edge_lengths[0]),
                int(rect_centre[1] - 0.5 * edge_lengths[1]),
                edge_lengths[0],
                edge_lengths[1],
            )
            painter.end()
