from pathlib import Path
from typing import Dict, Generator, List, Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from smartem.data_model import ParticleSet, ParticleSetLinker
from smartem.data_model.extract import DataAPI
from smartem.gui.qt.component_tab import ComponentTab
from smartem.parsing.star import (
    get_column_data,
    get_columns,
    insert_exposure_data,
    insert_particle_data,
    insert_particle_set,
    open_star_file,
)


def _string_to_glob(glob_string: str) -> Generator[Path, None, None]:
    split_string = glob_string.split("/")
    if "*" in split_string[0]:
        return Path("/").glob("/".join(split_string)[1:])
    root_path = Path("/")
    end_index = 0
    for i, s in enumerate(split_string):
        if "*" not in s:
            root_path = root_path / s
        else:
            end_index = i
            break
    print(root_path, "/".join(split_string[end_index:]))
    return root_path.glob("/".join(split_string[end_index:]))


class StarDataLoader(ComponentTab):
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

        star_lbl = QLabel()
        star_lbl.setText("Star file:")
        column_lbl = QLabel()
        column_lbl.setText("Data column:")

        self._file_combo = QComboBox()
        self._file_combo.setEditable(True)
        self._file_combo.currentIndexChanged.connect(self._select_star_file)

        star_hbox = QHBoxLayout()
        star_hbox.addWidget(star_lbl, 1)
        star_hbox.addWidget(self._file_combo, 1)

        self._file_vbox = QVBoxLayout()
        self._file_vbox.addLayout(star_hbox, 1)

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

    def _set_project_directory(self, project_directory: Path):
        self._proj_dir = project_directory
        for sf in self._proj_dir.glob("*/*/*.star"):
            str_sf = str(sf)
            if (
                all(p not in str_sf for p in ("gui", "pipeline", "Nodes", "NODES"))
                and "job" not in sf.name
                and not sf.parent.is_symlink()
            ):
                self._file_combo.addItem(str_sf)

    def _select_star_file(
        self,
        index: int,
        column_combos: Optional[List[QComboBox]] = None,
        defaults: Optional[List[str]] = None,
        connections: Optional[Dict[str, str]] = None,
    ):
        if "*" in self._file_combo.currentText():
            star_file_path = next(_string_to_glob(self._file_combo.currentText()))
        else:
            star_file_path = Path(self._file_combo.currentText())
        try:
            star_file = open_star_file(star_file_path)
        except (OSError, ValueError):
            print(f"Could not open star file {star_file_path}")
            return
        if not column_combos:
            column_combos = [self._column_combo]
        columns = get_columns(star_file, ignore=["pipeline"])
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
        raise NotImplementedError


class ExposureDataLoader(StarDataLoader):
    def __init__(
        self,
        extractor: DataAPI,
        project_directory: Optional[Path] = None,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(extractor, project_directory, refreshers=refreshers)
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

    def _select_star_file(
        self,
        index: int,
        column_combos: Optional[List[QComboBox]] = None,
        defaults: Optional[List[str]] = None,
        connections: Optional[Dict[str, str]] = None,
    ):
        super()._select_star_file(
            index,
            column_combos=column_combos
            or [self._column_combo, self._exposure_tag_combo],
            defaults=defaults or ["", "_rlnmicrographname"],
            connections=connections or {"_rlnmicrographname": "_exposure_tag"},
        )

    def _insert_from_star_file(self, star_file_path: Path):
        if self._exposure_tag:
            star_file = open_star_file(star_file_path)
            column_data = get_column_data(
                star_file, [self._exposure_tag, self._column], "micrographs"
            )
            insert_exposure_data(
                column_data, self._exposure_tag, str(star_file_path), self._extractor
            )

    def load(self):
        if (
            self._exposure_tag or self._exposure_tag_combo.currentText()
        ) and self._column:
            if not self._exposure_tag:
                self._exposure_tag = self._exposure_tag_combo.currentText()
            if "*" in self._file_combo.currentText():
                for sfp in _string_to_glob(self._file_combo.currentText()):
                    if not sfp.parent.is_symlink():
                        self._insert_from_star_file(Path(sfp))
            else:
                print("insert from", self._file_combo.currentText())
                self._insert_from_star_file(Path(self._file_combo.currentText()))
            self.refresh()


class ParticleDataLoader(ExposureDataLoader):
    def __init__(
        self,
        extractor: DataAPI,
        project_directory: Optional[Path] = None,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(extractor, project_directory, refreshers=refreshers)

        x_lbl = QLabel()
        x_lbl.setText("x coordinate identifier:")

        self._x_tag_combo = QComboBox()
        self._x_tag_combo.setEditable(True)
        self._x_tag_combo.currentIndexChanged.connect(self._select_x_tag)

        x_hbox = QHBoxLayout()
        x_hbox.addWidget(x_lbl, 1)
        x_hbox.addWidget(self._x_tag_combo, 1)

        self._identifier_box.addLayout(x_hbox, 1)

        y_lbl = QLabel()
        y_lbl.setText("y coordinate identifier:")

        self._y_tag_combo = QComboBox()
        self._y_tag_combo.setEditable(True)
        self._y_tag_combo.currentIndexChanged.connect(self._select_y_tag)

        y_hbox = QHBoxLayout()
        y_hbox.addWidget(y_lbl, 1)
        y_hbox.addWidget(self._y_tag_combo, 1)

        self._identifier_box.addLayout(y_hbox, 1)

    def _select_x_tag(self, index: int):
        self._x_tag = self._x_tag_combo.currentText()

    def _select_y_tag(self, index: int):
        self._y_tag = self._y_tag_combo.currentText()

    def _select_star_file(
        self,
        index: int,
        column_combos: Optional[List[QComboBox]] = None,
        defaults: Optional[List[str]] = None,
        connections: Optional[Dict[str, str]] = None,
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
            defaults=defaults
            or ["", "_rlnmicrographname", "_rlncoordinatex", "_rlncoordinatey"],
            connections=connections
            or {
                "_rlnmicrographname": "_exposure_tag",
                "_rlncoordinatex": "_x_tag",
                "_rlncoordinatey": "_y_tag",
            },
        )

    def _insert_from_star_file(
        self, star_file_path: Path, just_particles: bool = False
    ):
        star_file = open_star_file(star_file_path)
        if self._exposure_tag:
            if just_particles:
                column_data = get_column_data(
                    star_file,
                    [self._exposure_tag, self._x_tag, self._y_tag],
                    "particles",
                )
                particles = insert_particle_data(
                    column_data,
                    self._exposure_tag,
                    self._x_tag,
                    self._y_tag,
                    str(star_file_path),
                    self._extractor,
                )
                source_set = ParticleSet(
                    group_name=str(star_file_path),
                    identifier=str(star_file_path),
                    project_name=self._extractor._project,
                )
                self._extractor.put([source_set])
                linkers = [
                    ParticleSetLinker(
                        set_name=str(star_file_path), particle_id=p.particle_id
                    )
                    for p in particles
                ]
                self._extractor.put(linkers)

            else:
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
                    just_particles=True,
                )

    def load(self):
        if self._exposure_tag and self._x_tag and self._y_tag and self._column:
            if "*" in self._file_combo.currentText():
                for sfp in _string_to_glob(self._file_combo.currentText()):
                    if not sfp.parent.is_symlink():
                        self._insert_from_star_file(Path(sfp))
            else:
                self._insert_from_star_file(Path(self._file_combo.currentText()))
        elif self._exposure_tag and self._x_tag and self._y_tag:
            if "*" in self._file_combo.currentText():
                for sfp in _string_to_glob(self._file_combo.currentText()):
                    if not sfp.parent.is_symlink():
                        self._insert_from_star_file(Path(sfp), just_particles=True)
            else:
                self._insert_from_star_file(
                    Path(self._file_combo.currentText()), just_particles=True
                )
        self.refresh()


class ParticleSetDataLoader(ParticleDataLoader):
    def __init__(
        self,
        extractor: DataAPI,
        project_directory: Optional[Path] = None,
        refreshers: Optional[List[ComponentTab]] = None,
    ):
        super().__init__(extractor, project_directory, refreshers=refreshers)

        self._group_name_box = QLineEdit()
        self.grid.addWidget(self._group_name_box, 5, 2)

        set_id_lbl = QLabel()
        set_id_lbl.setText("Particle set identifier:")

        self._set_id_combo = QComboBox()
        self._set_id_combo.setEditable(True)
        self._set_id_combo.currentIndexChanged.connect(self._select_set_id_tag)

        set_id_hbox = QHBoxLayout()
        set_id_hbox.addWidget(set_id_lbl, 1)
        set_id_hbox.addWidget(self._set_id_combo, 1)

        self._identifier_box.addLayout(set_id_hbox, 1)

        cross_ref_lbl = QLabel()
        cross_ref_lbl.setText("Cross reference column:")

        self._cross_ref_combo = QComboBox()
        self._cross_ref_combo.setEditable(True)
        self._cross_ref_combo.setEnabled(False)

        cross_ref_hbox = QHBoxLayout()
        cross_ref_hbox.addWidget(cross_ref_lbl, 1)
        cross_ref_hbox.addWidget(self._cross_ref_combo, 1)

        self._identifier_box.addLayout(cross_ref_hbox, 1)

        cross_ref_file_hbox = QHBoxLayout()

        cross_ref_file_lbl = QLabel()
        cross_ref_file_lbl.setText("Star file for cross reference:")
        cross_ref_file_hbox.addWidget(cross_ref_file_lbl, 1)

        self._cross_ref_file_combo = QComboBox()
        self._cross_ref_file_combo.setEditable(True)
        self._cross_ref_file_combo.currentIndexChanged.connect(
            self._select_cross_ref_file
        )

        cross_ref_file_hbox.addWidget(self._cross_ref_file_combo, 1)

        self._file_vbox.addLayout(cross_ref_file_hbox, 1)

    def _set_project_directory(self, project_directory: Path):
        self._proj_dir = project_directory
        self._file_combo.clear()
        self._cross_ref_file_combo.clear()
        self._cross_ref_file_combo.addItem("")
        for sf in self._proj_dir.glob("*/*/*.star"):
            str_sf = str(sf)
            if (
                all(p not in str_sf for p in ("gui", "pipeline", "Nodes", "NODES"))
                and "job" not in sf.name
                and not sf.parent.is_symlink()
            ):
                self._file_combo.addItem(str_sf)
                self._cross_ref_file_combo.addItem(str_sf)

    def _select_cross_ref_file(self):
        if self._cross_ref_file_combo.currentText():
            self._cross_ref_combo.setEnabled(True)
            star_file_path = Path(self._cross_ref_file_combo.currentText())
            try:
                star_file = open_star_file(star_file_path)
            except (OSError, ValueError):
                print(f"Could not open star file {star_file_path}")
                return
            columns = get_columns(star_file, ignore=["pipeline"])
            self._cross_ref_combo.clear()
            self._column_combo.clear()
            for c in sorted(set(columns)):
                self._cross_ref_combo.addItem(c)
                if c == "_rlnreferenceimage":
                    self._cross_ref_combo.setCurrentText(c)
                self._column_combo.addItem(c)

    def _select_set_id_tag(self, index: int):
        self._set_id_tag = self._set_id_combo.currentText()

    def _select_star_file(
        self,
        index: int,
        column_combos: Optional[List[QComboBox]] = None,
        defaults: Optional[List[str]] = None,
        connections: Optional[Dict[str, str]] = None,
    ):
        if self._cross_ref_file_combo.currentText():
            self._cross_ref_combo.clear()
            super()._select_star_file(
                index,
                column_combos=column_combos
                or [
                    self._exposure_tag_combo,
                    self._x_tag_combo,
                    self._y_tag_combo,
                    self._set_id_combo,
                ],
                defaults=defaults
                or [
                    "_rlnmicrographname",
                    "_rlncoordinatex",
                    "_rlncoordinatey",
                    "_rlnclassnumber",
                ],
                connections=connections
                or {
                    "_rlnmicrographname": "_exposure_tag",
                    "_rlncoordinatex": "_x_tag",
                    "_rlncoordinatey": "_y_tag",
                    "_rlnclassnumber": "_set_id_tag",
                },
            )
            star_file_path = Path(self._cross_ref_file_combo.currentText())
            try:
                star_file = open_star_file(star_file_path)
            except (OSError, ValueError):
                return
            columns = get_columns(star_file, ignore=["pipeline"])
            self._cross_ref_combo.clear()
            self._column_combo.clear()
            for c in sorted(set(columns)):
                self._cross_ref_combo.addItem(c)
                if c == "_rlnreferenceimage":
                    self._cross_ref_combo.setCurrentText(c)
                self._column_combo.addItem(c)
        else:
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
                defaults=defaults
                or [
                    "",
                    "_rlnmicrographname",
                    "_rlncoordinatex",
                    "_rlncoordinatey",
                    "_rlnclassnumber",
                ],
            )

    def _insert_from_star_file(
        self,
        star_file_path: Path,
        just_particles: bool = False,
        cross_ref_file_path: Optional[Path] = None,
    ):
        if self._exposure_tag and self._column:
            if cross_ref_file_path:
                star_file = open_star_file(star_file_path)
                column_data = get_column_data(
                    star_file,
                    [
                        self._exposure_tag,
                        self._x_tag,
                        self._y_tag,
                        self._set_id_tag,
                        # self._cross_ref_combo.currentText(),
                    ],
                    "particles",
                )
                cross_ref_file = open_star_file(cross_ref_file_path)
                cross_ref_column_data = get_column_data(
                    cross_ref_file,
                    [self._cross_ref_combo.currentText(), self._column],
                    "model_classes",
                )
                for v in cross_ref_column_data.values():
                    for i, elem in enumerate(v):
                        if isinstance(elem, str) and "@" in elem:
                            _elem = elem.split("@")[0]
                            while _elem.startswith("0"):
                                _elem = _elem[1:]
                            v[i] = _elem
                cross_ref_dict = {}
                for i, k02 in enumerate(column_data[self._set_id_tag]):
                    for j, k01 in enumerate(
                        cross_ref_column_data[self._cross_ref_combo.currentText()]
                    ):
                        if k01 == str(k02):
                            cross_ref_dict[i] = cross_ref_column_data[self._column][j]
                column_data[self._column] = [
                    cross_ref_dict[i] for i in range(len(column_data[self._set_id_tag]))
                ]
                insert_particle_set(
                    column_data,
                    self._group_name_box.text(),
                    self._set_id_tag,
                    self._exposure_tag,
                    self._x_tag,
                    self._y_tag,
                    str(star_file_path),
                    self._extractor,
                    add_source_to_id=True,
                )
            else:
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
                    add_source_to_id=True,
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
            if "*" in self._file_combo.currentText():
                if "*" in self._cross_ref_file_combo.currentText():
                    split_file_name = self._file_combo.currentText().split("*")
                    for sfp in _string_to_glob(self._file_combo.currentText()):
                        if not sfp.parent.is_symlink():
                            wildcard = (
                                str(sfp)
                                .replace(split_file_name[0], "")
                                .replace(split_file_name[-1], "")
                            )
                            self._insert_from_star_file(
                                sfp,
                                cross_ref_file_path=Path(
                                    self._cross_ref_file_combo.currentText().replace(
                                        "*", wildcard
                                    )
                                ),
                            )
                elif self._cross_ref_file_combo.currentText():
                    for sfp in _string_to_glob(self._file_combo.currentText()):
                        if not sfp.parent.is_symlink():
                            self._insert_from_star_file(
                                Path(sfp),
                                cross_ref_file_path=Path(
                                    self._cross_ref_file_combo.currentText()
                                ),
                            )
                else:
                    for sfp in _string_to_glob(self._file_combo.currentText()):
                        if not sfp.parent.is_symlink():
                            self._insert_from_star_file(Path(sfp))
            elif self._cross_ref_file_combo.currentText():
                self._insert_from_star_file(
                    Path(self._file_combo.currentText()),
                    cross_ref_file_path=Path(self._cross_ref_file_combo.currentText()),
                )
            else:
                self._insert_from_star_file(Path(self._file_combo.currentText()))
            self.refresh()
