from __future__ import annotations

import importlib.resources

import matplotlib

matplotlib.use("Qt5Agg")
from pathlib import Path
from typing import List, Optional

from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import smartem.gui
from smartem.data_model import Project
from smartem.data_model.extract import DataAPI
from smartem.gui.qt.component_tab import ComponentTab
from smartem.gui.qt.display import AtlasDisplay, MainDisplay
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
        self.window.resize(1600, 900)
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
        self._data_loader.project = self._project_name
        self._csv_data_loader.project = self._project_name
        self._particle_loader.project = self._project_name
        self._particle_set_loader.project = self._project_name

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
        parse_epu_dir(Path(self.epu_dir), self._extractor, self._project_name)
        self._main_display._set_epu_directory(Path(self.epu_dir))
        self._main_display._set_data_size(Path(self.project_dir))
        self._main_display.set_project(self._project_name)
        self._atlas_display.project = self._project_name
        self.refresh()
        self._update_loaders()

    def load(self):
        atlas_found = self._extractor.set_project(self._project_name)
        if not atlas_found:
            raise ValueError("Atlas record not found")
        self._main_display._set_epu_directory(Path(self.epu_dir))
        self._main_display._set_data_size(Path(self.project_dir))
        self._main_display.set_project(self._project_name)
        self._atlas_display.project = self._project_name
        self.refresh()
        self._update_loaders()

    def _create_and_gather(self):
        self._create_project()
        gather_relion_defaults(
            Path(self.project_dir), self._extractor, self._project_name
        )
        self.refresh()

    def refresh(self):
        super().refresh()
        self._main_display.load()
        self._atlas_display.load(Path(self.epu_dir))
