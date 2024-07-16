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
        names = [gs.name for gs in atlas_data.grid_squares]
        df = pd.DataFrame(
            {
                "x": [gs.position_x for gs in atlas_data.grid_squares],
                "y": [gs.position_y for gs in atlas_data.grid_squares],
                "name": names,
                "score": [gs.score for gs in atlas_data.grid_squares],
            }
        )
        im = px.imshow(imdata)
        scatter = px.scatter(
            df, x="x", y="y", size="score", hover_data=["name"], size_max=10
        )
        im.add_traces(list(scatter.select_traces()))
        im.update_layout(
            coloraxis_showscale=False, height=800, xaxis_range=[0, len(imdata)]
        )

        def _set_record(click_data: dict):
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

        solara.FigurePlotly(im, on_click=_set_record)
    return main
