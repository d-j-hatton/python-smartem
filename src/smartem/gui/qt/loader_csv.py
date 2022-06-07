import csv
from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from smartem.data_model.extract import DataAPI
from smartem.gui.qt.component_tab import ComponentTab
from smartem.parsing.star import insert_exposure_data


class CSVDataLoader(ComponentTab):
    def __init__(
        self,
        extractor: DataAPI,
        project_directory: Optional[Path] = None,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(refreshers=refreshers)
        self._extractor = extractor
        self.grid = QGridLayout()
        self.setLayout(self.grid)
        self._exposure_tag = None
        self._column = None
        self._proj_dir = project_directory

        csv_lbl = QLabel()
        csv_lbl.setText("CSV file:")
        column_lbl = QLabel()
        column_lbl.setText("Data column:")

        self._file_combo = QComboBox()
        self._file_combo.setEditable(True)
        self._file_combo.currentIndexChanged.connect(self._select_csv_file)

        csv_hbox = QHBoxLayout()
        csv_hbox.addWidget(csv_lbl, 1)
        csv_hbox.addWidget(self._file_combo, 1)

        self._file_vbox = QVBoxLayout()
        self._file_vbox.addLayout(csv_hbox, 1)

        self.grid.addLayout(self._file_vbox, 2, 1, 1, 2)
        self._column_combo = QComboBox()
        self._column_combo.setEditable(True)
        self._column_combo.currentIndexChanged.connect(self._select_column)

        column_hbox = QHBoxLayout()
        column_hbox.addWidget(column_lbl, 1)
        column_hbox.addWidget(self._column_combo, 1)

        self.grid.addLayout(column_hbox, 3, 1, 1, 2)

        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self.load)
        self.grid.addWidget(load_btn, 5, 1)

        exposure_lbl = QLabel()
        exposure_lbl.setText("Micrograph identifier:")

        self._exposure_tag_combo = QComboBox()
        self._exposure_tag_combo.setEditable(True)
        self._exposure_tag_combo.currentIndexChanged.connect(self._select_exposure_tag)

        self._identifier_box = QVBoxLayout()

        hbox = QHBoxLayout()
        hbox.addWidget(exposure_lbl, 1)
        hbox.addWidget(self._exposure_tag_combo, 1)

        self._identifier_box.addLayout(hbox, 1)

        self.grid.addLayout(self._identifier_box, 4, 1, 1, 2)

        self._exposure_tag = self._exposure_tag_combo.currentText()

    def _select_exposure_tag(self, index: int):
        self._exposure_tag = self._exposure_tag_combo.currentText()

    def _set_project_directory(self, project_directory: Path):
        self._proj_dir = project_directory
        for sf in self._proj_dir.glob("*/*/*.csv"):
            str_sf = str(sf)
            self._file_combo.addItem(str_sf)

    def _insert_from_csv_file(self, csv_file_path: Path):
        if self._exposure_tag and self._column:
            column_data: Dict[str, List[str]] = {
                self._exposure_tag: [],
                self._column: [],
            }
            with open(csv_file_path, newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    column_data[self._exposure_tag].append(row[self._exposure_tag])
                    column_data[self._column].append(row[self._column])
            insert_exposure_data(
                column_data,
                self._exposure_tag,
                str(csv_file_path),
                self._extractor,
                extra_suffix="_grouped",
            )

    def _select_csv_file(
        self,
        index: int,
        defaults: Optional[List[str]] = None,
        connections: Optional[Dict[str, str]] = None,
    ):
        csv_file_path = Path(self._file_combo.currentText())
        with open(csv_file_path, newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            columns = list(next(reader).keys())
        column_combos = [self._column_combo, self._exposure_tag_combo]
        for combo in column_combos:
            combo.clear()
            combo.addItem("")
        for c in sorted(set(columns)):
            for i, combo in enumerate(column_combos):
                combo.addItem(c)
                if defaults and c == defaults[i]:
                    combo.setCurrentText(c)
                    if connections and connections.get(defaults[i]):
                        setattr(self, connections[defaults[i]], c)

    def _select_column(self, index: int):
        self._column = self._column_combo.currentText()

    def load(self, **kwargs):
        if (
            self._exposure_tag or self._exposure_tag_combo.currentText()
        ) and self._column:
            if not self._exposure_tag:
                self._exposure_tag = self._exposure_tag_combo.currentText()
            self._insert_from_csv_file(Path(self._file_combo.currentText()))
            self.refresh()
