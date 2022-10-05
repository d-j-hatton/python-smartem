from __future__ import annotations

import matplotlib
import matplotlib.ticker as mticker
import mrcfile

matplotlib.use("Qt5Agg")
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import PyQt5.QtCore as QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtGui import QPixmap, QTransform
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from smartem.data_model import Atlas, Exposure, FoilHole, GridSquare
from smartem.data_model.extract import DataAPI
from smartem.data_model.structure import (
    extract_keys,
    extract_keys_with_foil_hole_averages,
    extract_keys_with_grid_square_averages,
)
from smartem.gui.qt.component_tab import ComponentTab
from smartem.gui.qt.image_utils import ImageLabel, ParticleImageLabel
from smartem.gui.qt.plotting_utils import InteractivePlot
from smartem.parsing.epu import calibrate_coordinate_system
from smartem.stage_model import StageCalibration

SLIDER_MAX_VALUE = 500


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
        self._square_combo.setEditable(True)
        self._square_combo.currentIndexChanged.connect(self._select_square)
        self._foil_hole_combo = QComboBox()
        self._foil_hole_combo.setEditable(True)
        self._foil_hole_combo.currentIndexChanged.connect(self._select_foil_hole)
        self._exposure_combo = QComboBox()
        self._exposure_combo.setEditable(True)
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

        self._square_slider = QSlider(QtCore.Qt.Horizontal)
        self._square_slider.setMaximum(SLIDER_MAX_VALUE)
        self._square_slider.setTickInterval(1)
        self._square_slider.setValue(SLIDER_MAX_VALUE)
        self._square_slider_maximum = 0.0
        self._for_removal = None
        self._square_slider.valueChanged.connect(self._square_slider_changed)
        self.grid.addWidget(self._square_slider, 5, 1)

        self._particle_diameter_slider = QSlider(QtCore.Qt.Vertical)
        self._particle_diameter_slider.setMaximum(100)
        self._particle_diameter_slider.setTickInterval(1)
        self._particle_diameter_slider.setValue(30)
        self._particle_diameter = 30
        self._particle_diameter_slider.valueChanged.connect(
            self._particle_diameter_slider_changed
        )
        self.grid.addWidget(self._particle_diameter_slider, 1, 4)

        self._particle_tick_boxes = (
            QCheckBox("Show particles"),
            QCheckBox("Flip x"),
            QCheckBox("Flip y"),
        )
        self._particle_tick_boxes[0].toggled.connect(self._draw_current_exposure)
        self._particle_tick_boxes[1].toggled.connect(self._draw_current_exposure)
        self._particle_tick_boxes[2].toggled.connect(self._draw_current_exposure)
        self._particle_diameter_label = QLabel("Diameter: \n? Angstroms")
        # self._particle_dia
        particles_vbox = QVBoxLayout()
        full_vbox = QVBoxLayout()
        particles_vbox.addWidget(self._particle_tick_boxes[0], 1)
        particles_vbox.addWidget(self._particle_tick_boxes[1], 2)
        particles_vbox.addWidget(self._particle_tick_boxes[2], 3)
        full_vbox.addLayout(particles_vbox, 1)
        full_vbox.addWidget(self._particle_diameter_label, 2)
        self.grid.addLayout(full_vbox, 1, 5)

        self.project = ""
        self._stage_calibration = StageCalibration()

    def load(self):
        self._grid_squares = self._extractor.get_grid_squares(project=self.project)
        self._square_combo.clear()
        for gs in self._grid_squares:
            self._square_combo.addItem(gs.grid_square_name)
        self._update_fh_choices(self._grid_squares[0].grid_square_name)
        self.refresh()

    def set_project(self, project: str):
        self.project = project
        _project = self._extractor.get_project(project_name=self.project)
        _epu_version = _project.acquisition_software_version
        if (
            int(_epu_version.split(".")[0]) >= 2
            and int(_epu_version.split(".")[1]) > 12
        ):
            self._particle_tick_boxes[2].setChecked(True)

    def _set_epu_directory(self, epu_dir: Path):
        self._epu_dir = epu_dir
        for dm in (epu_dir.parent / "Metadata").glob("*.dm"):
            cal = calibrate_coordinate_system(dm)
            if cal:
                self._stage_calibration = cal
                break

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
        _atlas = self._extractor.get_atlases(project=self.project)
        atlas_sql_data = self._extractor.get_atlas_info(
            _atlas.atlas_id,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        extracted_atlas_data = extract_keys_with_grid_square_averages(
            atlas_sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        atlas_data = {k: v.flattened_data for k, v in extracted_atlas_data.items()}
        grid_square_averages = {k: v.averages for k, v in extracted_atlas_data.items()}
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
        extracted_grid_square_data = extract_keys_with_foil_hole_averages(
            sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        self._data = {
            k: v.flattened_data for k, v in extracted_grid_square_data.items()
        }
        self._foil_hole_averages = {
            k: v.averages for k, v in extracted_grid_square_data.items()
        }

    def _square_slider_changed(self, value: int):
        # print((value/100)*self._square_slider_maximum)
        try:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()],
                foil_hole=self._foil_holes[self._foil_hole_combo.currentIndex()],
                max_value=(value / SLIDER_MAX_VALUE) * self._square_slider_maximum,
            )
        except IndexError:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()],
                max_value=(value / SLIDER_MAX_VALUE) * self._square_slider_maximum,
            )
        if self._for_removal is not None:
            self._for_removal.remove()
        self._for_removal = self._grid_square_stats_fig.axvline(
            (value / SLIDER_MAX_VALUE) * self._square_slider_maximum
        )
        self._grid_square_stats.draw()

    def _particle_diameter_slider_changed(self, value: int):
        self._particle_diameter = value
        self._draw_current_exposure()
        exposure_pixmap = QPixmap(
            str(
                self._epu_dir
                / self._exposures[self._exposure_combo.currentIndex()].thumbnail
            )
        )
        qsize = exposure_pixmap.size()
        scaled_pixel_size = self._exposures[
            self._exposure_combo.currentIndex()
        ].pixel_size * (
            self._exposures[self._exposure_combo.currentIndex()].readout_area_x
            / qsize.width()
        )
        self._particle_diameter_label.setText(
            f"Diameter: \n{int(self._particle_diameter*scaled_pixel_size*10)} Angstroms"
        )

    def _gather_foil_hole_data(self):
        sql_data = self._extractor.get_foil_hole_info(
            self._foil_hole_combo.currentText(),
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        key_extracted_data = extract_keys(
            sql_data,
            self._exposure_keys,
            self._particle_keys,
            self._particle_set_keys,
        )
        try:
            self._update_foil_hole_stats(key_extracted_data)
        except KeyError:
            pass

    def _gather_data(self, evt):
        self._square_slider.setValue(SLIDER_MAX_VALUE)
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

        self._gather_grid_square_data()

        self._gather_foil_hole_data()

        self._data_gathered = True

        self._draw_foil_hole(
            self._foil_holes[self._foil_hole_combo.currentIndex()], flip=(-1, -1)
        )
        try:
            self._draw_exposure(
                self._exposures[self._exposure_combo.currentIndex()],
                flip=(
                    -1 if self._particle_tick_boxes[1].isChecked() else 1,
                    -1 if self._particle_tick_boxes[2].isChecked() else 1,
                ),
            )
        except IndexError:
            print(
                f"No exposure images for {self._foil_holes[self._foil_hole_combo.currentIndex()].foil_hole_name}"
            )

        try:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()],
                foil_hole=self._foil_holes[self._foil_hole_combo.currentIndex()],
            )
        except IndexError:
            self._draw_grid_square(
                self._grid_squares[self._square_combo.currentIndex()]
            )
        self._update_grid_square_stats(self._data)

        self._gather_atlas_data()

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
        self._grid_square_stats = InteractivePlot(gs_fig)
        self.grid.addWidget(self._grid_square_stats, 4, 1)
        try:
            if self._colour_bar:
                self._colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._grid_square_stats.set_data(list(stats.values())[0])
            self._grid_square_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
            self._grid_square_stats_fig.axes.set_xlabel(list(stats.keys())[0])
            self._square_slider_maximum = max(list(stats.values())[0])
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._grid_square_stats.set_data(data)
            self._grid_square_stats_fig.scatter(
                data[0],
                data[1],
                color="darkturquoise",
            )
            self._grid_square_stats_fig.axes.set_xlabel(labels[0])
            self._grid_square_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(list(v))
            for i, _ in enumerate(data):
                data[i] = np.nan_to_num(_)
            corr = np.corrcoef(data)
            mat = self._grid_square_stats_fig.matshow(corr)
            ticks_loc = (
                self._grid_square_stats_fig.axes.get_xticks(),
                self._grid_square_stats_fig.axes.get_yticks(),
            )
            self._grid_square_stats.set_data(corr)
            self._grid_square_stats_fig.xaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[0][1:-1])
            )
            self._grid_square_stats_fig.yaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[1][1:-1])
            )
            self._grid_square_stats_fig.axes.set_xticklabels(labels, rotation=45)
            self._grid_square_stats_fig.axes.set_yticklabels(labels)
            self._colour_bar = self._grid_square_stats_fig.figure.colorbar(mat)
        self._grid_square_stats.draw()

    def _update_foil_hole_stats(self, stats: Dict[str, List[float]]):
        fh_fig = Figure(tight_layout=True)
        fh_fig.set_facecolor("gray")
        self._foil_hole_stats_fig = fh_fig.add_subplot(111)
        self._foil_hole_stats_fig.set_facecolor("silver")
        self._foil_hole_stats = InteractivePlot(fh_fig)
        self.grid.addWidget(self._foil_hole_stats, 4, 2)
        try:
            if self._fh_colour_bar:
                self._fh_colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._foil_hole_stats.set_data(list(stats.values())[0])
            self._foil_hole_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
            self._foil_hole_stats_fig.axes.set_xlabel(list(stats.keys())[0])
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._foil_hole_stats.set_data(data)
            self._foil_hole_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._foil_hole_stats_fig.axes.set_xlabel(labels[0])
            self._foil_hole_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(list(v))
            corr = np.corrcoef(data)
            mat = self._foil_hole_stats_fig.matshow(corr)
            ticks_loc = (
                self._foil_hole_stats_fig.axes.get_xticks(),
                self._foil_hole_stats_fig.axes.get_yticks(),
            )
            self._foil_hole_stats.set_data(corr)
            self._foil_hole_stats_fig.xaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[0][1:-1])
            )
            self._foil_hole_stats_fig.yaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[1][1:-1])
            )
            self._foil_hole_stats_fig.axes.set_xticklabels(labels, rotation=45)
            self._foil_hole_stats_fig.axes.set_yticklabels(labels)
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
        self._exposure_stats = InteractivePlot(ex_fig)
        self.grid.addWidget(self._exposure_stats, 4, 3)
        try:
            if self._exp_colour_bar:
                self._exp_colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(stats.keys()) == 1:
            self._exposure_stats.set_data(list(stats.values())[0])
            self._exposure_stats_fig.hist(
                list(stats.values())[0], color="darkturquoise"
            )
            self._exposure_stats_fig.axes.set_xlabel(list(stats.keys())[0])
        if len(stats.keys()) == 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(v)
            self._exposure_stats.set_data(data)
            self._exposure_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._exposure_stats_fig.axes.set_xlabel(labels[0])
            self._exposure_stats_fig.axes.set_ylabel(labels[1])
        if len(stats.keys()) > 2:
            labels = []
            data = []
            for k, v in stats.items():
                labels.append(k)
                data.append(list(v))
            corr = np.corrcoef(data)
            mat = self._exposure_stats_fig.matshow(corr)
            ticks_loc = (
                self._exposure_stats_fig.axes.get_xticks(),
                self._exposure_stats_fig.axes.get_yticks(),
            )
            self._exposure_stats.set_data(corr)
            self._exposure_stats_fig.xaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[0][1:-1])
            )
            self._exposure_stats_fig.yaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[1][1:-1])
            )
            self._exposure_stats_fig.axes.set_xticklabels(labels, rotation=45)
            self._exposure_stats_fig.axes.set_yticklabels(labels)
            self._exp_colour_bar = self._exposure_stats_fig.figure.colorbar(mat)

        self._exposure_stats.draw()

    def _draw_grid_square(
        self,
        grid_square: GridSquare,
        foil_hole: Optional[FoilHole] = None,
        flip: Tuple[int, int] = (1, 1),
        max_value: Optional[float] = None,
    ) -> QLabel:
        if not self._epu_dir or not grid_square.thumbnail:
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
                    and fh.thumbnail
                    or fh.adjusted_stage_position_x is not None
                ]
                if max_value is not None:
                    imvs = [
                        i if i is not None and i < max_value else None for i in imvs
                    ]
                    if (
                        list(self._foil_hole_averages.values())[0][
                            foil_hole.foil_hole_name
                        ]
                        > max_value
                    ):
                        _key = None
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
                extra_images=[
                    fh
                    for fh in self._foil_holes
                    if fh != foil_hole
                    and fh.thumbnail
                    or fh.adjusted_stage_position_x is not None
                ],
                image_values=imvs,
                selection_box=self._square_combo,
                stage_calibration=self._stage_calibration,
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
        if foil_hole.thumbnail:
            hole_pixmap = QPixmap(str(self._epu_dir / foil_hole.thumbnail))
            if flip != (1, 1):
                hole_pixmap = hole_pixmap.transformed(QTransform().scale(*flip))
        if exposure and self._epu_dir:
            if foil_hole.thumbnail:
                qsize = hole_pixmap.size()
                hole_lbl = ImageLabel(
                    foil_hole,
                    exposure,
                    (qsize.width(), qsize.height()),
                    self._epu_dir,
                    parent=self,
                    selection_box=self._foil_hole_combo,
                    stage_calibration=self._stage_calibration,
                    draw=False,
                )
                self.grid.addWidget(hole_lbl, 1, 2)
                hole_lbl.setPixmap(hole_pixmap)
            else:
                hole_lbl = QLabel(self)
        else:
            hole_lbl = QLabel(self)
            if foil_hole.thumbnail:
                hole_lbl.setPixmap(hole_pixmap)
        return hole_lbl

    def _select_exposure(self, index: int):
        exposure_lbl = QLabel(self)
        try:
            exposure_lbl = self._draw_exposure(
                self._exposures[index],
                flip=(
                    -1 if self._particle_tick_boxes[1].isChecked() else 1,
                    -1 if self._particle_tick_boxes[2].isChecked() else 1,
                ),
            )
        except IndexError:
            return
        self.grid.addWidget(exposure_lbl, 1, 3)
        if self._foil_holes:
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
            key_extracted_data = extract_keys(
                sql_data,
                [],
                self._particle_keys,
                self._particle_set_keys,
            )
            self._update_exposure_stats(key_extracted_data)

    def _draw_current_exposure(self):
        try:
            self._draw_exposure(
                self._exposures[self._exposure_combo.currentIndex()],
                flip=(
                    -1 if self._particle_tick_boxes[1].isChecked() else 1,
                    -1 if self._particle_tick_boxes[2].isChecked() else 1,
                ),
            )
        except IndexError:
            return

    def _draw_exposure(
        self, exposure: Exposure, flip: Tuple[int, int] = (1, 1)
    ) -> QLabel:
        if not self._epu_dir or not exposure.thumbnail:
            return
        exposure_pixmap = QPixmap(str(self._epu_dir / exposure.thumbnail))
        if flip != (1, 1):
            exposure_pixmap = exposure_pixmap.transformed(QTransform().scale(*flip))
        qsize = exposure_pixmap.size()
        particles = []
        if self._particle_tick_boxes[0].isChecked():
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
            selection_box=self._exposure_combo,
            particle_diameter=self._particle_diameter,
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

        self._data_keys["micrograph"] = self._extractor.get_exposure_keys(self.project)
        self._data_keys["particle"] = self._extractor.get_particle_keys(self.project)
        self._data_keys["particle_set"] = self._extractor.get_particle_set_keys(
            self.project
        )
        for keys in self._data_keys.values():
            for k in keys:
                self._data_list.addItem(k)

        # self._pick_keys["source"] = self._extractor.get_particle_info_sources(
        #     self.project
        # )
        self._pick_keys["set_group"] = self._extractor.get_particle_set_group_names(
            self.project
        )
        for keys in self._pick_keys.values():
            for k in keys:
                self._pick_list.addItem(k)


class AtlasDisplay(ComponentTab):
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
        self.project = ""

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
        self._atlas_stats = InteractivePlot(atlas_fig)
        try:
            if self._colour_bar:
                self._colour_bar.remove()
        except (AttributeError, ValueError):
            pass
        if len(self._data.keys()) == 1:
            self._atlas_stats.set_data(list(self._data.values())[0])
            self._atlas_stats_fig.hist(
                list(self._data.values())[0], color="darkturquoise"
            )
            self._atlas_stats_fig.axes.set_xlabel(list(self._data.keys())[0])
        if len(self._data.keys()) == 2:
            labels = []
            data = []
            for k, v in self._data.items():
                labels.append(k)
                data.append(v)
            self._atlas_stats.set_data(data)
            self._atlas_stats_fig.scatter(data[0], data[1], color="darkturquoise")
            self._atlas_stats_fig.axes.set_xlabel(labels[0])
            self._atlas_stats_fig.axes.set_ylabel(labels[1])
        if len(self._data.keys()) > 2:
            labels = []
            data = []
            for k, v in self._data.items():
                labels.append(k)
                data.append(list(v))
            corr = np.corrcoef(data)
            mat = self._atlas_stats_fig.matshow(corr)
            ticks_loc = (
                self._atlas_stats_fig.axes.get_xticks(),
                self._atlas_stats_fig.axes.get_yticks(),
            )
            self._atlas_stats.set_data(corr)
            self._atlas_stats_fig.xaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[0][1:-1])
            )
            self._atlas_stats_fig.yaxis.set_major_locator(
                mticker.FixedLocator(ticks_loc[1][1:-1])
            )
            self._atlas_stats_fig.axes.set_xticklabels(labels, rotation=45)
            self._atlas_stats_fig.axes.set_yticklabels(labels)
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
        _atlases = self._extractor.get_atlases(project=self.project)
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
            (grid_square.stage_position_x, grid_square.stage_position_y),
            project=self.project,
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
