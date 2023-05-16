from pathlib import Path

import matplotlib.pyplot as plt
import mrcfile
import numpy as np

from smartem.parsing.epu import (
    metadata_foil_hole_positions,
    metadata_foil_hole_stage,
    metadata_grid_square_positions,
    metadata_grid_square_stage,
    parse_epu_xml,
)


class Atlas:
    def __init__(
        self, atlas_epu_dir: Path, sample: int, epu_data_dir: Path | None = None
    ):
        atlas_epu_dir = Path(atlas_epu_dir)
        self._epu_data_dir = epu_data_dir
        self._atlas_location = atlas_epu_dir / f"Sample{sample}" / "Atlas"
        epu_data = parse_epu_xml(self._atlas_location / "Atlas_1.xml")
        self._pixel_size = epu_data["pixel_size"]
        self._readout_area = epu_data["readout_area"]
        self._grid_square_positions = metadata_grid_square_positions(
            self._atlas_location / "Atlas.dm"
        )

    @property
    def image(self) -> np.array:
        with mrcfile.open(self._atlas_location / "Atlas_1.mrc") as mrc:
            data = mrc.data
        return data

    @property
    def _grid_square_stage_locations(self) -> dict:
        return metadata_grid_square_stage(self._atlas_location / "Atlas.dm")

    def stage_correction(self):
        vals_x = []
        vals_y = []
        stage = self._grid_square_stage_locations
        for gs, c in self._grid_square_positions.items():
            stage_x = (
                int((-stage[gs][0]) / self._pixel_size) + self._readout_area[0] // 2
            )
            vals_x.append(stage_x - c[0])
            stage_y = (
                int((stage[gs][1]) / self._pixel_size) + self._readout_area[1] // 2
            )
            vals_y.append(stage_y - c[1])
        return ((np.mean(vals_x), np.std(vals_x)), (np.mean(vals_y), np.std(vals_y)))

    def display(
        self,
        show_squares: bool = True,
        show_stage_positions: bool = True,
    ):

        corrected_center = ((0, 0), (0, 0))

        # fig, ax = plt.subplots(1, figsize=(12, 6))
        fig = plt.figure(1)
        ax = fig.gca()
        ax.imshow(self.image)

        self._readout_area = self.image.shape

        annot = ax.annotate(
            "Grid square ID: ", xy=(0, 0), xytext=(5, 5), textcoords="offset points"
        )
        annot.set_visible(False)

        labels: dict = {}
        scatters: dict = {}
        lines: dict = {}
        lines_list: list = []

        def hover(event):
            if event.inaxes == ax:
                for sc, c in scatters.items():
                    cont, ind = sc.contains(event)
                    if cont:
                        # annot.xy = (event.xdata, event.ydata)
                        annot_text = f"Grid square ID: {', '.join([str(labels[sc][n]) for n in ind['ind']])}"
                        annot.set_text(annot_text)
                        annot.set_color(c)
                        annot.set_visible(True)
                        break
                    else:
                        annot.set_visible(False)
                fig.canvas.draw()

        def click(event):
            if event.inaxes == ax:
                for sc, c in scatters.items():
                    cont, ind = sc.contains(event)
                    if cont and self._epu_data_dir:
                        gs = GridSquare(
                            self._epu_data_dir, int(labels[sc][ind["ind"][0]])
                        )
                        gs.display()

        def on_pick(event):
            legline = event.artist
            origline = lines[legline]
            visible = not origline.get_visible()
            origline.set_visible(visible)
            legline.set_alpha(1.0 if visible else 0.2)
            fig.canvas.draw()

        if show_squares:
            squares_sc = ax.scatter(
                [p[0] for p in self._grid_square_positions.values()],
                [p[1] for p in self._grid_square_positions.values()],
                marker="x",
                color="green",
                label="Pixel",
            )
            scatters[squares_sc] = "green"
            labels[squares_sc] = list(self._grid_square_positions.keys())
            lines_list.append(squares_sc)

        if show_stage_positions:
            stage_data = self._grid_square_stage_locations
            keys = list(stage_data.keys())
            gs = keys[0]
            stage_sc = ax.scatter(
                [
                    int((-p[0]) / self._pixel_size)
                    - corrected_center[0][0]
                    + self._readout_area[1] // 2
                    for p in stage_data.values()
                ],
                [
                    int(p[1] / self._pixel_size)
                    + corrected_center[1][0]
                    + self._readout_area[0] // 2
                    for p in stage_data.values()
                ],
                marker="x",
                color="red",
                label="Stage from atlas mag",
            )
            scatters[stage_sc] = "red"
            labels[stage_sc] = keys
            lines_list.append(stage_sc)
        if self._epu_data_dir:
            grid_squares = []
            for gs in self._grid_square_positions.keys():
                if GridSquare.found(self._epu_data_dir, int(gs)):
                    grid_squares.append(GridSquare(self._epu_data_dir, int(gs)))
            gs_sc = ax.scatter(
                [
                    int((-p._stage_position[0]) / self._pixel_size)
                    - corrected_center[0][0]
                    + self._readout_area[1] // 2
                    for p in grid_squares
                ],
                [
                    int((p._stage_position[1]) / self._pixel_size)
                    + corrected_center[1][0]
                    + self._readout_area[0] // 2
                    for p in grid_squares
                ],
                marker="x",
                color="blue",
                label="Stage from grid square mag",
            )
            scatters[gs_sc] = "blue"
            labels[gs_sc] = [gs._id for gs in grid_squares]
            lines_list.append(gs_sc)

        leg = ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        for legline, origline in zip(leg.legendHandles, lines_list):
            legline.set_picker(True)
            lines[legline] = origline
        fig.canvas.mpl_connect("motion_notify_event", hover)
        fig.canvas.mpl_connect("button_press_event", click)
        fig.canvas.mpl_connect("pick_event", on_pick)
        fig.show()
        plt.show()
        plt.close(fig)


class GridSquare:
    def __init__(self, epu_dir: Path, grid_square: int, images_disc: int = 1):
        epu_dir = Path(epu_dir)
        self._id = grid_square
        self._epu_location = (
            epu_dir / f"Images-Disc{images_disc}" / f"GridSquare_{grid_square}"
        )
        xml_file = list(self._epu_location.glob("*.xml"))[0]
        epu_data = parse_epu_xml(xml_file)
        self._pixel_size = epu_data["pixel_size"]
        self._readout_area = epu_data["readout_area"]
        self._stage_position = epu_data["stage_position"]
        self._foil_hole_positions = metadata_foil_hole_positions(
            epu_dir / "Metadata" / f"GridSquare_{grid_square}.dm"
        )
        self._foil_hole_stage_locations = metadata_foil_hole_stage(
            epu_dir / "Metadata" / f"GridSquare_{grid_square}.dm"
        )

    @classmethod
    def found(cls, epu_dir: Path, grid_square: int, images_disc: int = 1) -> bool:
        epu_dir = Path(epu_dir)
        return (
            epu_dir / f"Images-Disc{images_disc}" / f"GridSquare_{grid_square}"
        ).is_dir()

    @property
    def image(self) -> np.array:
        img_file = list(self._epu_location.glob("*.mrc"))[0]
        with mrcfile.open(img_file) as mrc:
            return mrc.data

    def display(
        self,
        show_holes: bool = True,
        show_stage_positions: bool = True,
        show_foil_hole_data: bool = True,
    ):
        # fig, ax = plt.subplots(1, figsize=(12, 6))
        fig = plt.figure(2)
        ax = fig.gca()
        ax.imshow(self.image)

        self._readout_area = self.image.shape

        annot = ax.annotate(
            "Grid square ID: ", xy=(0, 0), xytext=(5, 5), textcoords="offset points"
        )
        annot.set_visible(False)

        labels: dict = {}
        scatters: dict = {}
        lines: dict = {}
        lines_list: list = []

        def hover(event):
            if event.inaxes == ax:
                for sc, c in scatters.items():
                    cont, ind = sc.contains(event)
                    if cont:
                        # annot.xy = (event.xdata, event.ydata)
                        annot_text = f"Foil hole ID: {', '.join([str(labels[sc][n]) for n in ind['ind']])}"
                        annot.set_text(annot_text)
                        annot.set_color(c)
                        annot.set_visible(True)
                        break
                    else:
                        annot.set_visible(False)
                fig.canvas.draw()

        def on_pick(event):
            legline = event.artist
            origline = lines[legline]
            visible = not origline.get_visible()
            origline.set_visible(visible)
            legline.set_alpha(1.0 if visible else 0.2)
            fig.canvas.draw()

        if show_holes:
            holes_sc = ax.scatter(
                [p[0] for p in self._foil_hole_positions.values()],
                [p[1] for p in self._foil_hole_positions.values()],
                marker="x",
                color="green",
                label="Pixel",
            )
            scatters[holes_sc] = "green"
            labels[holes_sc] = list(self._foil_hole_positions.keys())
            lines_list.append(holes_sc)

        if show_stage_positions:
            stage_sc = ax.scatter(
                [
                    int((-p[0]) / self._pixel_size)
                    + int(self._stage_position[0] / self._pixel_size)
                    + self._readout_area[1] // 2
                    for p in self._foil_hole_stage_locations.values()
                ],
                [
                    int((p[1]) / self._pixel_size)
                    - (self._stage_position[1] / self._pixel_size)
                    + self._readout_area[0] // 2
                    for p in self._foil_hole_stage_locations.values()
                ],
                marker="x",
                color="red",
                label="Stage from grid square mag",
            )
            scatters[stage_sc] = "red"
            labels[stage_sc] = list(self._foil_hole_stage_locations.keys())
            lines_list.append(stage_sc)

        if show_foil_hole_data:
            foil_holes = []
            found_foil_holes = []
            for fh in self._foil_hole_positions.keys():
                fh_xmls = list(
                    (self._epu_location / "FoilHoles").glob(f"FoilHole_{fh}*.xml")
                )
                if fh_xmls:
                    foil_holes.append(parse_epu_xml(fh_xmls[0]))
                    found_foil_holes.append(fh)
            fh_sc = ax.scatter(
                [
                    int((-p["stage_position"][0]) / self._pixel_size)
                    + (self._stage_position[0] / self._pixel_size)
                    + self._readout_area[1] // 2
                    for p in foil_holes
                ],
                [
                    int((p["stage_position"][1]) / self._pixel_size)
                    - (self._stage_position[1] / self._pixel_size)
                    + self._readout_area[0] // 2
                    for p in foil_holes
                ],
                marker="x",
                color="blue",
                label="Stage from foil hole mag",
            )
            scatters[fh_sc] = "blue"
            labels[fh_sc] = found_foil_holes
            lines_list.append(fh_sc)

        leg = ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
        for legline, origline in zip(leg.legendHandles, lines_list):
            legline.set_picker(True)
            lines[legline] = origline
        fig.canvas.mpl_connect("motion_notify_event", hover)
        fig.canvas.mpl_connect("pick_event", on_pick)
        plt.show()
        plt.close(fig)
