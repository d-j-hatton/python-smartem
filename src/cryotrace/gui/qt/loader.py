from pathlib import Path
from typing import List, Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from cryotrace.data_model.extract import Extractor
from cryotrace.parsing.star import (
    get_column_data,
    get_columns,
    insert_exposure_data,
    insert_particle_data,
    insert_particle_set,
    open_star_file,
)


class StarDataLoader(QWidget):
    def __init__(self, extractor: Extractor, project_directory: Optional[Path] = None):
        super().__init__()
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._exposure_tag = None
        self._column = None
        self._proj_dir = project_directory

        star_lbl = QLabel()
        star_lbl.setText("Star file:")
        self.grid.addWidget(star_lbl, 2, 1)
        column_lbl = QLabel()
        column_lbl.setText("Data column:")
        self.grid.addWidget(column_lbl, 3, 1)

        self._file_combo = QComboBox()
        self._file_combo.setEditable(True)
        self._file_combo.currentIndexChanged.connect(self._select_star_file)
        self.grid.addWidget(self._file_combo, 2, 2)
        self._column_combo = QComboBox()
        self._column_combo.setEditable(True)
        self._column_combo.currentIndexChanged.connect(self._select_column)
        self.grid.addWidget(self._column_combo, 3, 2)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load)
        self.grid.addWidget(load_btn, 5, 2)

    def _set_project_directory(self, project_directory: Path):
        self._proj_dir = project_directory
        for sf in self._proj_dir.glob("*/*/*.star"):
            str_sf = str(sf)
            if (
                all(p not in str_sf for p in ("gui", "pipeline", "Nodes", "NODES"))
                and "job" not in sf.name
            ):
                self._file_combo.addItem(str_sf)

    def _select_star_file(
        self, index: int, column_combos: Optional[List[QComboBox]] = None
    ):
        star_file_path = Path(self._file_combo.currentText())
        try:
            star_file = open_star_file(star_file_path)
        except (OSError, ValueError):
            return
        if not column_combos:
            column_combos = [self._column_combo]
        columns = get_columns(star_file, ignore=["pipeline"])
        for combo in column_combos:
            combo.clear()
        for c in columns:
            for combo in column_combos:
                combo.addItem(c)

    def _select_column(self, index: int):
        self._column = self._column_combo.currentText()

    def load(self, **kwargs):
        raise NotImplementedError


class ExposureDataLoader(StarDataLoader):
    def __init__(self, extractor: Extractor, project_directory: Optional[Path] = None):
        super().__init__(extractor, project_directory)
        exposure_lbl = QLabel()
        exposure_lbl.setText("Micrograph identifier:")
        self.grid.addWidget(exposure_lbl, 4, 1)

        self._exposure_tag_combo = QComboBox()
        self._exposure_tag_combo.setEditable(True)
        self._exposure_tag_combo.currentIndexChanged.connect(self._select_exposure_tag)
        self.grid.addWidget(self._exposure_tag_combo, 4, 2)

        self._exposure_tag = self._exposure_tag_combo.currentText()

    def _select_exposure_tag(self, index: int):
        self._exposure_tag = self._exposure_tag_combo.currentText()

    def _select_star_file(
        self, index: int, column_combos: Optional[List[QComboBox]] = None
    ):
        super()._select_star_file(
            index,
            column_combos=column_combos
            or [self._column_combo, self._exposure_tag_combo],
        )

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


class ParticleDataLoader(ExposureDataLoader):
    def __init__(self, extractor: Extractor, project_directory: Optional[Path] = None):
        super().__init__(extractor, project_directory)

        x_lbl = QLabel()
        x_lbl.setText("x coordinate identifier:")
        self.grid.addWidget(x_lbl, 4, 3)

        self._x_tag_combo = QComboBox()
        self._x_tag_combo.setEditable(True)
        self._x_tag_combo.currentIndexChanged.connect(self._select_x_tag)
        self.grid.addWidget(self._x_tag_combo, 4, 4)

        y_lbl = QLabel()
        y_lbl.setText("y coordinate identifier:")
        self.grid.addWidget(y_lbl, 4, 5)

        self._y_tag_combo = QComboBox()
        self._y_tag_combo.setEditable(True)
        self._y_tag_combo.currentIndexChanged.connect(self._select_y_tag)
        self.grid.addWidget(self._y_tag_combo, 4, 6)

    def _select_x_tag(self, index: int):
        self._x_tag = self._x_tag_combo.currentText()

    def _select_y_tag(self, index: int):
        self._y_tag = self._y_tag_combo.currentText()

    def _select_star_file(
        self, index: int, column_combos: Optional[List[QComboBox]] = None
    ):
        super()._select_star_file(
            index,
            column_combos=column_combos
            or [
                self._column_combo,
                self._exposure_tag_combo,
                self._x_tag_combo,
                self._y_tag_combo,
            ],
        )

    def load(self):
        if self._exposure_tag and self._x_tag and self._y_tag and self._column:
            star_file_path = Path(self._file_combo.currentText())
            star_file = open_star_file(star_file_path)
            column_data = get_column_data(
                star_file,
                [self._exposure_tag, self._x_tag, self._y_tag, self._column],
                "particles",
            )
            insert_particle_data(
                column_data,
                self._exposure_tag,
                self._x_tag,
                self._y_tag,
                str(star_file_path),
                self._extractor,
            )
        elif self._exposure_tag and self._x_tag and self._y_tag:
            star_file_path = Path(self._file_combo.currentText())
            star_file = open_star_file(star_file_path)
            column_data = get_column_data(
                star_file, [self._exposure_tag, self._x_tag, self._y_tag], "particles"
            )
            insert_particle_data(
                column_data,
                self._exposure_tag,
                self._x_tag,
                self._y_tag,
                str(star_file_path),
                self._extractor,
                just_particles=True,
            )


class ParticleSetDataLoader(ParticleDataLoader):
    def __init__(self, extractor: Extractor, project_directory: Optional[Path] = None):
        super().__init__(extractor, project_directory)

        self._group_name_box = QLineEdit()
        self.grid.addWidget(self._group_name_box, 5, 2)

        set_id_lbl = QLabel()
        set_id_lbl.setText("Particle set identifier:")
        self.grid.addWidget(set_id_lbl, 4, 7)

        self._set_id_combo = QComboBox()
        self._set_id_combo.setEditable(True)
        self._set_id_combo.currentIndexChanged.connect(self._select_set_id_tag)
        self.grid.addWidget(self._set_id_combo, 4, 8)

    def _select_set_id_tag(self, index: int):
        self._set_id_tag = self._set_id_combo.currentText()

    def _select_star_file(
        self, index: int, column_combos: Optional[List[QComboBox]] = None
    ):
        super()._select_star_file(
            index,
            column_combos=column_combos
            or [
                self._column_combo,
                self._exposure_tag_combo,
                self._x_tag_combo,
                self._y_tag_combo,
                self._set_id_combo,
            ],
        )

    def load(self):
        if (
            self._exposure_tag
            and self._x_tag
            and self._y_tag
            and self._column
            and self._set_id_tag
            and self._group_name_box.text()
        ):
            star_file_path = Path(self._file_combo.currentText())
            star_file = open_star_file(star_file_path)
            column_data = get_column_data(
                star_file,
                [
                    self._exposure_tag,
                    self._x_tag,
                    self._y_tag,
                    self._column,
                    self._set_id_tag,
                ],
                "particles",
            )
            insert_particle_set(
                column_data,
                self._group_name_box.text(),
                self._set_id_tag,
                self._exposure_tag,
                self._x_tag,
                self._y_tag,
                str(star_file_path),
                self._extractor,
            )
