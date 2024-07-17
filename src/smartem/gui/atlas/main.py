import json
import os
from pathlib import Path
from typing import List

import mrcfile
import pandas as pd
import plotly.express as px
import solara
import tifffile
from pydantic import BaseModel

recording = solara.Reactive("Good")
good_records = solara.Reactive([])
bad_records = solara.Reactive([])
max_size = solara.Reactive(10)
num_suggested = solara.Reactive(15)
records = {"Good": good_records, "Bad": bad_records}


class GridSquare(BaseModel):
    name: str
    position_x: int
    position_y: int
    score: float


class AtlasScores(BaseModel):
    image_path: Path
    grid_squares: List[GridSquare]


def _read_atlas_data(atlas_json_path: Path) -> AtlasScores:
    with open(atlas_json_path) as js:
        data = json.load(js)
    return AtlasScores(**data)


@solara.component
def Page():
    with solara.HBox() as main:
        with solara.Card("Record"):
            with solara.VBox():
                solara.ToggleButtonsSingle(value=recording, values=["Good", "Bad"])
                for r in records[recording.value].value:
                    solara.Markdown(r)
        file_path = Path(os.environ["SMARTEM_ATLAS_BASEPATH"]) / "atlas.json"
        atlas_data = _read_atlas_data(file_path)
        if atlas_data.image_path.suffix == ".mrc":
            imdata = mrcfile.read(atlas_data.image_path)
        else:
            imdata = tifffile.imread(atlas_data.image_path)
        imdata_full = imdata.copy()
        imdata = imdata[::10, ::10]
        names = [gs.name for gs in atlas_data.grid_squares]
        score_threshold = sorted([gs.score for gs in atlas_data.grid_squares])[
            -num_suggested.value
        ]
        df = pd.DataFrame(
            {
                "x": [gs.position_x // 10 for gs in atlas_data.grid_squares],
                "y": [gs.position_y // 10 for gs in atlas_data.grid_squares],
                "name": names,
                "score": [gs.score for gs in atlas_data.grid_squares],
                "suggested": [
                    gs.score >= score_threshold for gs in atlas_data.grid_squares
                ],
            }
        )
        im = px.imshow(imdata)
        im_full = px.imshow(imdata_full)
        im_full.update_layout(
            coloraxis_showscale=False, height=800, xaxis_range=[0, len(imdata_full)]
        )
        scatter = px.scatter(
            df,
            x="x",
            y="y",
            size="score",
            hover_data=["name"],
            size_max=max_size.value,
            color="suggested",
        )
        im.add_traces(list(scatter.select_traces()))
        im.update_layout(
            coloraxis_showscale=False, height=800, xaxis_range=[0, len(imdata)]
        )

        def _set_record(click_data: dict):
            try:
                clicked_name = names[click_data["points"]["point_indexes"][0]]
                if clicked_name in records[recording.value].value:
                    records[recording.value].value = [
                        r for r in records[recording.value].value if r != clicked_name
                    ]
                else:
                    records[recording.value].value = [
                        *records[recording.value].value,
                        clicked_name,
                    ]
            except Exception:
                return

        with solara.VBox():
            solara.SliderInt("Size", value=max_size, min=1, max=30, step=5)
            solara.SliderInt(
                "No. of suggested squares",
                value=num_suggested,
                min=1,
                max=len(atlas_data.grid_squares),
            )
            with solara.HBox():
                solara.FigurePlotly(im, on_click=_set_record)
                solara.FigurePlotly(im_full)
    return main
