import json
import os
from pathlib import Path
from typing import Dict, List

import mrcfile
import numpy as np
import pandas as pd
import plotly.express as px
import solara
import tifffile
import yaml
from pydantic import BaseModel

recording = solara.Reactive("Good")
good_records = solara.Reactive([])
bad_records = solara.Reactive([])
max_size = solara.Reactive(10)
num_suggested = solara.Reactive(15)
records = {"Good": good_records, "Bad": bad_records}


class GridSquare(BaseModel):
    name: str
    position_x: float
    position_y: float
    score: float


class AtlasScores(BaseModel):
    image_path: Path
    grid_squares: List[GridSquare]


def _read_atlas_data(atlas_json_path: Path) -> AtlasScores:
    with open(atlas_json_path) as js:
        data = json.load(js)
    return AtlasScores(**data)


class GUIConfig(BaseModel):
    json_path_pattern: str
    pattern_options: Dict[str, List[str]]


def _read_config(config_path: Path) -> GUIConfig:
    with open(config_path) as y:
        data = yaml.safe_load(y)
    return GUIConfig(**data)


pattern_options = {}
config = _read_config(Path(os.environ["SMARTEM_GUI_CONFIG"]))
for k, v in config.pattern_options.items():
    if v:
        pattern_options[k] = solara.Reactive(v[0])
    else:
        pattern_options[k] = solara.Reactive("")


def _get_json_glob(pattern: str) -> str:
    elements = [p.split("}")[0] for p in pattern.split("{")[1:]]
    for e in elements:
        pattern = pattern.replace(f"{{{e}}}", pattern_options[e].value)
    return pattern


file_path_str = solara.Reactive("")
found_json = solara.Reactive([])


@solara.component
def Page():
    with solara.HBox() as main:
        json_glob = _get_json_glob(config.json_path_pattern)
        json_glob_parts = json_glob.split("/")
        first_wildcard_index = json_glob_parts.index(
            [p for p in json_glob_parts if "*" in p][0]
        )
        found_json = [
            str(p)
            for p in Path("/".join(json_glob_parts[:first_wildcard_index])).glob(
                "/".join(json_glob_parts[first_wildcard_index:])
            )
        ]

        file_path = Path(file_path_str.value) if file_path_str.value else None

        def _save_record():
            if file_path:
                with open(
                    file_path.parent / f"{file_path.stem}-annotated.json", "w"
                ) as js:
                    annotation_data = {
                        "good": good_records.value,
                        "bad": bad_records.value,
                    }
                    json.dump(annotation_data, js)

        with solara.Card("Record"):
            with solara.VBox():
                solara.ToggleButtonsSingle(value=recording, values=["Good", "Bad"])
                for r in records[recording.value].value:
                    solara.Markdown(r)
                solara.Button(label="Save", on_click=_save_record)
        if file_path:
            atlas_data = _read_atlas_data(file_path)
            if atlas_data.image_path.suffix == ".mrc":
                imdata = mrcfile.read(atlas_data.image_path)
            else:
                imdata = tifffile.imread(atlas_data.image_path)
            imdata_full = imdata.copy()
            imdata = imdata[::10, ::10]
            names = [gs.name for gs in atlas_data.grid_squares]
            try:
                score_threshold = sorted([gs.score for gs in atlas_data.grid_squares])[
                    -num_suggested.value
                ]
            except IndexError:
                score_threshold = sorted([gs.score for gs in atlas_data.grid_squares])[
                    -1
                ]
            scores = [gs.score for gs in atlas_data.grid_squares]
            scores -= np.min(scores)
            scores /= np.max(scores)
            df = pd.DataFrame(
                {
                    "x": [int(gs.position_x / 10) for gs in atlas_data.grid_squares],
                    "y": [int(gs.position_y / 10) for gs in atlas_data.grid_squares],
                    "name": names,
                    "score": scores,
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
                            r
                            for r in records[recording.value].value
                            if r != clicked_name
                        ]
                    else:
                        records[recording.value].value = [
                            *records[recording.value].value,
                            clicked_name,
                        ]
                except Exception:
                    return

        with solara.VBox():
            for k, v in pattern_options.items():
                if all(config.pattern_options[k]):
                    solara.Select(label=k, value=v, values=config.pattern_options[k])
                else:
                    solara.InputText(k, value=v)
            solara.Select(label="Atlas data", value=file_path_str, values=found_json)
            if file_path:
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
