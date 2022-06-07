from __future__ import annotations

import importlib.resources

import matplotlib
import mrcfile

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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import smartem.gui
from smartem.data_model import Atlas, Exposure, FoilHole, GridSquare, Project
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import (
    extract_keys,
    extract_keys_with_foil_hole_averages,
    extract_keys_with_grid_square_averages,
)
from smartem.gui.qt.component_tab import ComponentTab
from smartem.gui.qt.image_utils import ImageLabel, ParticleImageLabel
from smartem.gui.qt.loader import (
    ExposureDataLoader,
    ParticleDataLoader,
    ParticleSetDataLoader,
)
from smartem.gui.qt.loader_csv import CSVDataLoader
from smartem.parsing.epu import create_atlas_and_tiles, parse_epu_dir, parse_epu_version
from smartem.parsing.relion_default import gather_relion_defaults


class App:
    def __init__(self, extractor: DataAPI):
        self.app = QApplication([])
        self.window = QtFrame(extractor)
        self.app.setStyleSheet(
            importlib.resources.read_text(smartem.gui.qt, "qt_style.css")
        )

    def start(self):
        self.window.show()
        self.app.exec()


class QtFrame(QWidget):
    def __init__(self, extractor: DataAPI):
        super().__init__()
        self.tabs = QTabWidget()
        self.layout = QVBoxLayout(self)
        atlas_display = AtlasDisplay(extractor)
        main_display = MainDisplay(extractor, atlas_view=atlas_display)
        data_loader = ExposureDataLoader(extractor, refreshers=[main_display])
        csv_data_loader = CSVDataLoader(extractor, refreshers=[main_display])
        particle_loader = ParticleDataLoader(extractor, refreshers=[main_display])
        particle_set_loader = ParticleSetDataLoader(
            extractor, refreshers=[main_display]
        )
        proj_loader = ProjectLoader(
            extractor,
            data_loader,
            csv_data_loader,
            particle_loader,
            particle_set_loader,
            main_display,
            atlas_display,
        )
        self.tabs.addTab(proj_loader, "Project")
        self.tabs.addTab(data_loader, "Load mic data")
        self.tabs.addTab(csv_data_loader, "Load mic data (CSV)")
        self.tabs.addTab(particle_loader, "Load particle data")
        self.tabs.addTab(particle_set_loader, "Load particle set data")
        self.tabs.addTab(main_display, "Grid square view")
        self.tabs.addTab(atlas_display, "Atlas view")
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)


class ProjectLoader(ComponentTab):
    def __init__(
        self,
        extractor: DataAPI,
        data_loader: ExposureDataLoader,
        csv_data_loader: CSVDataLoader,
        particle_loader: ParticleDataLoader,
        particle_set_loader: ParticleSetDataLoader,
        main_display: MainDisplay,
        atlas_display: AtlasDisplay,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(refreshers=refreshers)
        self._extractor = extractor
        self._data_loader = data_loader
        self._csv_data_loader = csv_data_loader
        self._particle_loader = particle_loader
        self._particle_set_loader = particle_set_loader
        self._main_display = main_display
        self._atlas_display = atlas_display
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self.epu_dir = ""
        self.project_dir = ""
        self._combo = QComboBox()
        projects = self._extractor.get_projects()
        self._combo.addItem(None)
        for proj in projects:
            self._combo.addItem(proj)
        self._combo.currentIndexChanged.connect(self._select_project)
        self._project_name = self._combo.currentText()
        self._name_input = QLineEdit()
        self._name_input.returnPressed.connect(self._button_check)
        hbox = QHBoxLayout()
        hbox.addWidget(self._combo, 1)
        hbox.addWidget(self._name_input, 1)
        self.grid.addLayout(hbox, 1, 1, 1, 2)
        epu_hbox = QHBoxLayout()
        epu_btn = QPushButton("Select EPU directory")
        epu_btn.clicked.connect(self._select_epu_dir)
        self.epu_lbl = QLabel()
        self.epu_lbl.setText(f"Selected: {self.epu_dir}")
        epu_hbox.addWidget(epu_btn, 1)
        epu_hbox.addWidget(self.epu_lbl, 1)
        self.grid.addLayout(epu_hbox, 2, 1, 1, 2)
        self.atlas = None
        atlas_hbox = QHBoxLayout()
        atlas_btn = QPushButton("Select Atlas")
        atlas_btn.clicked.connect(self._select_atlas)
        self.atlas_lbl = QLabel()
        self.atlas_lbl.setText(f"Selected: {self.atlas}")
        atlas_hbox.addWidget(atlas_btn, 1)
        atlas_hbox.addWidget(self.atlas_lbl, 1)
        self.grid.addLayout(atlas_hbox, 3, 1, 1, 2)
        project_hbox = QHBoxLayout()
        project_btn = QPushButton("Select project directory")
        project_btn.clicked.connect(self._select_processing_project)
        self.project_lbl = QLabel()
        self.project_lbl.setText(f"Selected: {self.project_dir}")
        project_hbox.addWidget(project_btn)
        project_hbox.addWidget(self.project_lbl)
        self.grid.addLayout(project_hbox, 4, 1, 1, 2)
        self._load_btn = QPushButton("Load")
        self._load_btn.clicked.connect(self.load)
        self.grid.addWidget(self._load_btn, 5, 1)
        self._create_btn = QPushButton("Create")
        self._create_btn.clicked.connect(self._create_project)
        self.grid.addWidget(self._create_btn, 5, 2)
        self._create_gather_btn = QPushButton("Create and load default data")
        self._create_gather_btn.clicked.connect(self._create_and_gather)
        self.grid.addWidget(self._create_gather_btn, 6, 2)
        self._button_check()

    def _button_check(self):
        if self._combo.currentText():
            self._load_btn.setEnabled(True)
            self._create_btn.setEnabled(False)
            self._create_gather_btn.setEnabled(False)
        elif self._name_input.text() and self.atlas and self.epu_dir:
            self._load_btn.setEnabled(False)
            self._create_btn.setEnabled(True)
            self._create_gather_btn.setEnabled(True)
        else:
            self._load_btn.setEnabled(False)
            self._create_btn.setEnabled(False)
            self._create_gather_btn.setEnabled(False)

    def _select_project(self):
        if self._combo.currentText():
            self._project_name = self._combo.currentText()
            self._name_input.setEnabled(False)
            project = self._extractor.get_project(project_name=self._project_name)
            atlas = self._extractor.get_atlas_from_project(project)
            self.epu_dir = project.acquisition_directory
            self.epu_lbl.setText(f"Selected: {self.epu_dir}")
            self.project_dir = project.processing_directory
            self.project_lbl.setText(f"Selected: {self.project_dir}")
            self.atlas = atlas.thumbnail
            self.atlas_lbl.setText(f"Selected: {self.atlas}")
        else:
            self._name_input.setEnabled(False)
            self._project_name = self._name_input.text()
        self._button_check()

    def _select_epu_dir(self):
        self.epu_dir = QFileDialog.getExistingDirectory(
            self, "Select EPU directory", ".", QFileDialog.ShowDirsOnly
        )
        self.epu_lbl.setText(f"Selected: {self.epu_dir}")
        self._button_check()

    def _select_atlas_combo(self, index: int):
        self.atlas = self._combo.currentText()
        self.atlas_lbl.setText(f"Selected: {self.atlas}")
        self._button_check()

    def _select_atlas(self):
        self.atlas = QFileDialog.getOpenFileName(self, "Select Atlas image", ".")[0]
        self.atlas_lbl.setText(f"Selected: {self.atlas}")
        self._button_check()

    def _select_processing_project(self):
        self.project_dir = QFileDialog.getExistingDirectory(
            self, "Select project directory", ".", QFileDialog.ShowDirsOnly
        )
        self.project_lbl.setText(f"Selected: {self.project_dir}")
        self._button_check()

    def _update_loaders(self):
        self._data_loader._set_project_directory(Path(self.project_dir))
        self._csv_data_loader._set_project_directory(Path(self.project_dir))
        self._particle_loader._set_project_directory(Path(self.project_dir))
        self._particle_set_loader._set_project_directory(Path(self.project_dir))

    def _create_project(self):
        self._project_name = self._name_input.text()
        found = self._extractor.set_project(self._project_name)
        if not found:
            _atlas_id = create_atlas_and_tiles(Path(self.atlas), self._extractor)
            software, version = parse_epu_version(Path(self.epu_dir))
            proj = Project(
                atlas_id=_atlas_id,
                acquisition_directory=self.epu_dir,
                project_name=self._project_name,
                processing_directory=self.project_dir,
                acquisition_software=software,
                acquisition_software_version=version,
            )
            self._extractor.put([proj])
        atlas_found = self._extractor.set_project(self._project_name)
        if not atlas_found:
            raise ValueError(
                "Project record not found despite having just been inserted"
            )
        parse_epu_dir(Path(self.epu_dir), self._extractor)
        self._main_display._set_epu_directory(Path(self.epu_dir))
        self._main_display._set_data_size(Path(self.project_dir))
        self.refresh()
        self._update_loaders()

    def load(self):
        atlas_found = self._extractor.set_project(self._project_name)
        if not atlas_found:
            raise ValueError("Atlas record not found")
        self._main_display._set_epu_directory(Path(self.epu_dir))
        self._main_display._set_data_size(Path(self.project_dir))
        self.refresh()
        self._update_loaders()

    def _create_and_gather(self):
        self._create_project()
        gather_relion_defaults(Path(self.project_dir), self._extractor)
        self.refresh()

    def refresh(self):
        super().refresh()
        self._main_display.load()
        self._atlas_display.load(Path(self.epu_dir))


class MainDisplay(ComponentTab):
    def __init__(
        self,
        extractor: DataAPI,
        atlas_view: Optional[AtlasDisplay] = None,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(refreshers=refreshers)
        self._extractor = extractor
        self._epu_dir: Optional[Path] = None
        self._data_size: Optional[Tuple[int, int]] = None
        self._data: Dict[str, List[float]] = {}
        self._foil_hole_averages: Dict[str, Dict[str, float]] = {}
        self._particle_data: Dict[str, List[float]] = {}
        self._exposure_keys: List[str] = []
        self._particle_keys: List[str] = []
        self._particle_set_keys: List[str] = []
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._square_combo = QComboBox()
        self._square_combo.currentIndexChanged.connect(self._select_square)
        self._foil_hole_combo = QComboBox()
        self._foil_hole_combo.currentIndexChanged.connect(self._select_foil_hole)
        self._exposure_combo = QComboBox()
        self._exposure_combo.currentIndexChanged.connect(self._select_exposure)
        self._data_combo = QComboBox()
        self._data_list = QListWidget()
        self._data_list.setSelectionMode(QListWidget.MultiSelection)
        self._pick_list = QListWidget()
        self._pick_list.setSelectionMode(QListWidget.MultiSelection)
        fh_fig = Figure()
        fh_fig.set_facecolor("gray")
        self._foil_hole_stats_fig = fh_fig.add_subplot(111)
        self._foil_hole_stats_fig.set_facecolor("silver")
        self._foil_hole_stats = FigureCanvasQTAgg(fh_fig)
        gs_fig = Figure()
        gs_fig.set_facecolor("gray")
        self._grid_square_stats_fig = gs_fig.add_subplot(111)
        self._grid_square_stats_fig.set_facecolor("silver")
        self._grid_square_stats = FigureCanvasQTAgg(gs_fig)
        ex_fig = Figure()
        ex_fig.set_facecolor("gray")
        self._exposure_stats_fig = ex_fig.add_subplot(111)
        self._exposure_stats_fig.set_facecolor("silver")
        self._exposure_stats = FigureCanvasQTAgg(ex_fig)
        self.grid.addWidget(self._square_combo, 2, 1)
        self.grid.addWidget(self._foil_hole_combo, 2, 2)
        self.grid.addWidget(self._exposure_combo, 2, 3)
        self.grid.addWidget(self._data_list, 3, 2)
        self.grid.addWidget(self._pick_list, 3, 3)
        self.grid.addWidget(self._grid_square_stats, 4, 1)
        self.grid.addWidget(self._foil_hole_stats, 4, 2)
        self.grid.addWidget(self._exposure_stats, 4, 3)
        self._grid_squares: List[GridSquare] = []
        self._foil_holes: List[FoilHole] = []
        self._exposures: List[Exposure] = []
        self._atlas_view = atlas_view
        self._colour_bar = None
        self._fh_colour_bar = None
        self._exp_colour_bar = None
        self._data_gathered = False
        self._data_keys: Dict[str, List[str]] = {
            "micrograph": [],
            "particle": [],
            "particle_set": [],
        }
        self._pick_keys: Dict[str, List[str]] = {
            "source": [],
            "set_group": [],
        }

        self._gather_btn = QPushButton("Gather data")
        self._gather_btn.clicked.connect(self._gather_data)
        self.grid.addWidget(self._gather_btn, 3, 1)

    def load(self):
        self._grid_squares = self._extractor.get_grid_squares()
        self._square_combo.clear()
        for gs in self._grid_squares:
            self._square_combo.addItem(gs.grid_square_name)
        self._update_fh_choices(self._grid_squares[0].grid_square_name)
        self.refresh()

    def _set_epu_directory(self, epu_dir: Path):
        self._epu_dir = epu_dir

    def _set_data_size(self, project_dir: Path):
        try:
            mcdir = project_dir / "MotionCorr" / "job002" / "Movies"
            first_mrc = next(iter(mcdir.glob("**/*.mrc")))
            with mrcfile.open(first_mrc) as mrc:
                self._data_size = mrc.data.shape
        except Exception:
            return

    def _gather_atlas_data(self):
        _grid_square = self._grid_squares[self._square_combo.currentIndex()]
        _atlas = self._extractor.get_atlases()
        atlas_exposures = self._extractor.get_exposures(atlas_id=_atlas.atlas_id)
        atlas_particles = self._extractor.get_particles(atlas_id=_atlas.atlas_id)
        atlas_sql_data = self._extractor.get_atlas_info(
            _atlas.atlas_id,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        atlas_data, grid_square_averages = extract_keys_with_grid_square_averages(
            atlas_sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
            atlas_exposures,
            atlas_particles,
        )
        if self._atlas_view and self._epu_dir:
            self._atlas_view._data = atlas_data
            self._atlas_view._grid_square_averages = grid_square_averages
            self._atlas_view.load(
                self._epu_dir,
                grid_square=_grid_square,
                all_grid_squares=self._grid_squares,
                data_changed=True,
            )

    def _gather_grid_square_data(self):
        foil_hole_exposures = {}
        for fh in self._foil_holes:
            foil_hole_exposures[fh.foil_hole_name] = [
                e.exposure_name
                for e in self._extractor.get_exposures(foil_hole_name=fh.foil_hole_name)
            ]

        sql_data = self._extractor.get_grid_square_info(
            self._square_combo.currentText(),
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        grid_square_exposures = self._extractor.get_exposures(
            grid_square_name=self._square_combo.currentText()
        )
        grid_square_particles = self._extractor.get_particles(
            grid_square_name=self._square_combo.currentText()
        )
        self._data, self._foil_hole_averages = extract_keys_with_foil_hole_averages(
            sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
            grid_square_exposures,
            grid_square_particles,
        )

    def _gather_foil_hole_data(self):
        sql_data = self._extractor.get_foil_hole_info(
            self._foil_hole_combo.currentText(),
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        foil_hole_exposures = self._extractor.get_exposures(
            foil_hole_name=self._foil_hole_combo.currentText()
        )
        foil_hole_particles = self._extractor.get_particles(
            foil_hole_name=self._foil_hole_combo.currentText()
        )
        key_extracted_data = extract_keys(
            sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
            foil_hole_exposures,
            foil_hole_particles,
        )
        try:
            self._update_foil_hole_stats(key_extracted_data)
        except KeyError:
            pass

    def _gather_data(self, evt):
        selected_keys = [d.text() for d in self._data_list.selectedItems()]
        self._exposure_keys = [
            k for k in selected_keys if k in self._data_keys["micrograph"]
        ]
        self._particle_keys = [
            k for k in selected_keys if k in self._data_keys["particle"]
        ]
        self._particle_set_keys = [
            k for k in selected_keys if k in self._data_keys["particle_set"]
        ]

        self._gather_atlas_data()

        self._gather_grid_square_data()

        self._gather_foil_hole_data()

        self._data_gathered = True

        try:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()],
                foil_hole=self._foil_holes[self._foil_hole_combo.currentIndex()],
            )
            self._draw_foil_hole(
                self._foil_holes[self._foil_hole_combo.currentIndex()], flip=(-1, -1)
            )
            self._draw_exposure(
                self._exposures[self._exposure_combo.currentIndex()], flip=(1, -1)
            )
        except IndexError:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()]
            )
        self._update_grid_square_stats(self._data)

    def _select_square(self, index: int):
        if self._data_gathered:
            self._gather_grid_square_data()
            self._update_grid_square_stats(self._data)
        try:
            square_lbl = self._draw_grid_square(
                self._grid_squares[index],
                foil_hole=self._foil_holes[self._foil_hole_combo.currentIndex()],
            )
        except IndexError:
            try:
                square_lbl = self._draw_grid_square(self._grid_squares[index])
            except IndexError:
                return
        self.grid.addWidget(square_lbl, 1, 1)
        self._update_fh_choices(self._square_combo.currentText())

        if self._atlas_view and self._epu_dir:
            self._atlas_view.load(
                self._epu_dir,
                grid_square=self._grid_squares[index],
                all_grid_squares=self._grid_squares,
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
        if (
            any([self._exposure_keys, self._particle_keys, self._particle_set_keys])
            and self._foil_hole_combo.currentText()
        ):
            self._gather_foil_hole_data()

    def _update_grid_square_stats(self, stats: Dict[str, List[float]]):
        gs_fig = Figure(tight_layout=True)
        gs_fig.set_facecolor("gray")
        self._grid_square_stats_fig = gs_fig.add_subplot(111)
        self._grid_square_stats_fig.set_facecolor("silver")
        self._grid_square_stats = FigureCanvasQTAgg(gs_fig)
        self.grid.addWidget(self._grid_square_stats, 4, 1)
        try:
            if self._colour_bar:
                self._colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._grid_square_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._grid_square_stats_fig.scatter(
                data[0],
                data[1],
                color="darkturquoise",
            )
            self._grid_square_stats_fig.axes.set_xlabel(labels[0])
            self._grid_square_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            data = [list(v) for v in list(stats.values())]
            for i, _ in enumerate(data):
                data[i] = np.nan_to_num(_)
            corr = np.corrcoef(data)
            mat = self._grid_square_stats_fig.matshow(corr)
            self._colour_bar = self._grid_square_stats_fig.figure.colorbar(mat)
        self._grid_square_stats.draw()

    def _update_foil_hole_stats(self, stats: Dict[str, List[float]]):
        fh_fig = Figure(tight_layout=True)
        fh_fig.set_facecolor("gray")
        self._foil_hole_stats_fig = fh_fig.add_subplot(111)
        self._foil_hole_stats_fig.set_facecolor("silver")
        self._foil_hole_stats = FigureCanvasQTAgg(fh_fig)
        self.grid.addWidget(self._foil_hole_stats, 4, 2)
        try:
            if self._fh_colour_bar:
                self._fh_colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._foil_hole_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._foil_hole_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._foil_hole_stats_fig.axes.set_xlabel(labels[0])
            self._foil_hole_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            data = [list(v) for v in list(stats.values())]
            corr = np.corrcoef(data)
            mat = self._foil_hole_stats_fig.matshow(corr)
            self._fh_colour_bar = self._foil_hole_stats_fig.figure.colorbar(mat)
        self._foil_hole_stats.draw()

    def _update_foil_hole_stats_picks(self, stats: Dict[str, List[int]]):
        if len(stats.keys()) == 2:
            size_lists = list(stats.values())
            diffs = [p2 - p1 for p1, p2 in zip(size_lists[0], size_lists[1])]
            self._foil_hole_stats_fig.hist(diffs)
            self._foil_hole_stats.draw()

    def _update_exposure_stats(self, stats: Dict[str, List[float]]):
        ex_fig = Figure(tight_layout=True)
        ex_fig.set_facecolor("gray")
        self._exposure_stats_fig = ex_fig.add_subplot(111)
        self._exposure_stats_fig.set_facecolor("silver")
        self._exposure_stats = FigureCanvasQTAgg(ex_fig)
        self.grid.addWidget(self._exposure_stats, 4, 3)
        try:
            if self._exp_colour_bar:
                self._exp_colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._exposure_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._exposure_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._exposure_stats_fig.axes.set_xlabel(labels[0])
            self._exposure_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            corr = np.corrcoef(list(stats.values()))
            mat = self._exposure_stats_fig.matshow(corr)
            self._exp_colour_bar = self._exposure_stats_fig.figure.colorbar(mat)

        self._exposure_stats.draw()

    def _draw_grid_square(
        self,
        grid_square: GridSquare,
        foil_hole: Optional[FoilHole] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> QLabel:
        if not self._epu_dir:
            return
        square_pixmap = QPixmap(str(self._epu_dir / grid_square.thumbnail))
        if flip != (1, 1):
            square_pixmap = square_pixmap.transformed(QTransform().scale(*flip))
        if foil_hole and self._epu_dir:
            qsize = square_pixmap.size()
            imvs: Optional[list] = None
            _key = None
            if len(self._data.keys()) == 1:
                _key = list(self._data.keys())[0]
                imvs = [
                    list(self._foil_hole_averages.values())[0].get(fh.foil_hole_name)
                    for fh in self._foil_holes
                    if fh != foil_hole
                ]
            square_lbl = ImageLabel(
                grid_square,
                foil_hole,
                (qsize.width(), qsize.height()),
                self._epu_dir,
                parent=self,
                value=list(self._foil_hole_averages.values())[0].get(
                    foil_hole.foil_hole_name
                )
                if _key
                else None,
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
        if not self._epu_dir:
            return
        hole_pixmap = QPixmap(str(self._epu_dir / foil_hole.thumbnail))
        if flip != (1, 1):
            hole_pixmap = hole_pixmap.transformed(QTransform().scale(*flip))
        if exposure and self._epu_dir:
            qsize = hole_pixmap.size()
            hole_lbl = ImageLabel(
                foil_hole,
                exposure,
                (qsize.width(), qsize.height()),
                self._epu_dir,
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
            _project = self._extractor.get_project()
            _epu_version = _project.acquisition_software_version
            if (
                int(_epu_version.split(".")[0]) >= 2
                and int(_epu_version.split(".")[1]) > 12
            ):
                exposure_lbl = self._draw_exposure(self._exposures[index], flip=(1, -1))
            else:
                exposure_lbl = self._draw_exposure(self._exposures[index], flip=(1, 1))
        except IndexError:
            return
        self.grid.addWidget(exposure_lbl, 1, 3)
        self._draw_foil_hole(
            self._foil_holes[self._foil_hole_combo.currentIndex()],
            exposure=self._exposures[index],
            flip=(-1, -1),
        )
        if (
            any([self._particle_keys, self._particle_set_keys])
            and self._exposure_combo.currentText()
        ):

            sql_data = self._extractor.get_exposure_info(
                self._exposure_combo.currentText(),
                self._particle_keys,
                self._particle_set_keys,
            )
            exposure_particles = self._extractor.get_particles(
                exposure_name=self._exposure_combo.currentText()
            )
            key_extracted_data = extract_keys(
                sql_data,
                [],
                self._particle_keys,
                self._particle_set_keys,
                [],
                exposure_particles,
            )
            self._update_exposure_stats(key_extracted_data)

    def _draw_exposure(
        self, exposure: Exposure, flip: Tuple[int, int] = (1, 1)
    ) -> QLabel:
        if not self._epu_dir:
            return
        exposure_pixmap = QPixmap(str(self._epu_dir / exposure.thumbnail))
        if flip != (1, 1):
            exposure_pixmap = exposure_pixmap.transformed(QTransform().scale(*flip))
        qsize = exposure_pixmap.size()
        particles = []
        if self._pick_list.selectedItems():
            for p in self._pick_list.selectedItems():
                if p.text() in self._pick_keys["source"]:
                    exp_parts = self._extractor.get_particles(
                        exposure_name=exposure.exposure_name, source=p.text()
                    )
                    particles.append(exp_parts)
                else:
                    exp_parts = self._extractor.get_particles(
                        exposure_name=exposure.exposure_name,  # group_name=p.text()
                    )
                    particles.append(exp_parts)
        else:
            particles = [
                self._extractor.get_particles(exposure_name=exposure.exposure_name)
            ]
        with mrcfile.open(
            (self._epu_dir / exposure.thumbnail).with_suffix(".mrc")
        ) as mrc:
            thumbnail_size = mrc.data.shape
        exposure_lbl = ParticleImageLabel(
            exposure,
            particles,
            (qsize.width(), qsize.height()),
            image_scale=0.5
            if self._data_size is None
            else thumbnail_size[0] / self._data_size[0],
        )
        self.grid.addWidget(exposure_lbl, 1, 3)
        exposure_lbl.setPixmap(exposure_pixmap)
        return exposure_lbl

    def _update_fh_choices(self, grid_square_name: str):
        self._foil_holes = self._extractor.get_foil_holes(
            grid_square_name=grid_square_name
        )
        self._foil_hole_combo.clear()
        for fh in self._foil_holes:
            self._foil_hole_combo.addItem(fh.foil_hole_name)

    def _update_exposure_choices(self, foil_hole_name: str):
        self._exposures = self._extractor.get_exposures(foil_hole_name=foil_hole_name)
        self._exposure_combo.clear()
        for ex in self._exposures:
            self._exposure_combo.addItem(ex.exposure_name)

    def refresh(self):
        super().refresh()
        self._data_list.clear()
        self._pick_list.clear()

        self._data_keys["micrograph"] = self._extractor.get_exposure_keys()
        self._data_keys["particle"] = self._extractor.get_particle_keys()
        self._data_keys["particle_set"] = self._extractor.get_particle_set_keys()
        for keys in self._data_keys.values():
            for k in keys:
                self._data_list.addItem(k)

        self._pick_keys["source"] = self._extractor.get_particle_info_sources()
        self._pick_keys["set_group"] = self._extractor.get_particle_set_group_names()
        for keys in self._pick_keys.values():
            for k in keys:
                self._pick_list.addItem(k)


class AtlasDisplay(QWidget):
    def __init__(self, extractor: DataAPI):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        atlas_fig = Figure(tight_layout=True)
        atlas_fig.set_facecolor("gray")
        self._atlas_stats_fig = atlas_fig.add_subplot(111)
        self._atlas_stats_fig.set_facecolor("silver")
        self._atlas_stats = FigureCanvasQTAgg(atlas_fig)
        self._data: Dict[str, List[float]] = {}
        self._grid_square_averages: Dict[str, Dict[str, float]] = {}
        self._particle_data: Dict[str, List[float]] = {}
        self._colour_bar = None
        self._grid_square: Optional[GridSquare] = None
        self._all_grid_squares: List[GridSquare] = []

    def load(
        self,
        epu_dir: Path,
        grid_square: Optional[GridSquare] = None,
        all_grid_squares: Optional[List[GridSquare]] = None,
        data_changed: bool = False,
    ):
        self._grid_square = grid_square
        self._all_grid_squares = all_grid_squares or []
        if data_changed:
            self._update_atlas_stats()
        atlas_lbl = self._draw_atlas(
            epu_dir,
            grid_square=self._grid_square,
            all_grid_squares=self._all_grid_squares,
        )
        if atlas_lbl:
            vbox = QVBoxLayout()
            vbox.addWidget(atlas_lbl)
            vbox.addStretch()
            self.grid.addLayout(vbox, 0, 0)
            if self._grid_square:
                tile_lbl = self._draw_tile(self._grid_square, epu_dir)
                vbox = QVBoxLayout()
                vbox.addWidget(tile_lbl)
                vbox.addWidget(self._atlas_stats)
                vbox.addStretch()
                self.grid.addLayout(vbox, 0, 1)

    def _update_atlas_stats(self):
        atlas_fig = Figure(tight_layout=True)
        atlas_fig.set_facecolor("gray")
        self._atlas_stats_fig = atlas_fig.add_subplot(111)
        self._atlas_stats_fig.set_facecolor("silver")
        self._atlas_stats = FigureCanvasQTAgg(atlas_fig)
        try:
            if self._colour_bar:
                self._colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(self._data.keys()) == 1:
            self._atlas_stats_fig.hist(
                list(self._data.values())[0], color="darkturquoise"
            )
        if len(self._data.keys()) == 2:
            labels = []
            data = []
            for k, v in self._data.items():
                labels.append(k)
                data.append(v)
            self._atlas_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._atlas_stats_fig.axes.set_xlabel(labels[0])
            self._atlas_stats_fig.axes.set_ylabel(labels[1])
        if len(self._data.keys()) > 2:
            data = [list(v) for v in list(self._data.values())]
            corr = np.corrcoef(data)
            mat = self._atlas_stats_fig.matshow(corr)
            self._colour_bar = self._atlas_stats_fig.figure.colorbar(mat)
        self._atlas_stats.draw()

    def _draw_atlas(
        self,
        epu_dir: Path,
        grid_square: Optional[GridSquare] = None,
        all_grid_squares: Optional[List[GridSquare]] = None,
        flip: Tuple[int, int] = (1, 1),
    ) -> Optional[QLabel]:
        _atlas: Optional[Atlas] = None
        _atlases = self._extractor.get_atlases()
        if isinstance(_atlases, Atlas):
            _atlas = _atlases
        elif _atlases:
            _atlas = _atlases[0]
        if _atlas:
            atlas_pixmap = QPixmap(_atlas.thumbnail)
            if flip != (1, 1):
                atlas_pixmap = atlas_pixmap.transformed(QTransform().scale(*flip))
            if grid_square:
                imvs: Optional[list] = None
                if (
                    self._data
                    and grid_square
                    and all_grid_squares
                    and len(self._data.keys()) == 1
                ):
                    imvs = [
                        list(self._grid_square_averages.values())[0].get(
                            gs.grid_square_name
                        )
                        for gs in all_grid_squares
                        if gs != grid_square
                    ]
                    imvs = list(np.nan_to_num(imvs))
                qsize = atlas_pixmap.size()
                atlas_lbl = ImageLabel(
                    _atlas,
                    grid_square,
                    (qsize.width(), qsize.height()),
                    epu_dir,
                    parent=self,
                    overwrite_readout=True,
                    value=list(self._grid_square_averages.values())[0].get(
                        grid_square.grid_square_name
                    )
                    if imvs
                    else None,
                    extra_images=[gs for gs in all_grid_squares if gs != grid_square]
                    if all_grid_squares
                    else [],
                    image_values=imvs,
                )
                atlas_lbl.setPixmap(atlas_pixmap)
            else:
                atlas_lbl = QLabel(self)
                atlas_lbl.setPixmap(atlas_pixmap)
            return atlas_lbl
        return None

    def _draw_tile(
        self, grid_square: GridSquare, epu_dir: Path, flip: Tuple[int, int] = (1, 1)
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
                _tile,
                grid_square,
                (qsize.width(), qsize.height()),
                epu_dir,
                parent=self,
            )
            tile_lbl.setPixmap(tile_pixmap)
            return tile_lbl
        return None
