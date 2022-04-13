from pathlib import Path

import xmltodict

from cryotrace.data_model import FoilHole, GridSquare
from cryotrace.data_model.extract import Extractor


def parse_epu_dir(epu_path: Path, extractor: Extractor):
    grid_squares = []
    foil_holes = []
    for grid_square_dir in epu_path.glob("GridSquare*"):
        if grid_square_dir.is_dir():
            grid_square_jpeg = next(grid_square_dir.glob("*.jpg"))
            with open(grid_square_jpeg.with_suffix(".xml"), "r") as xml:
                for_parsing = xml.read()
                grid_square_data = xmltodict.parse(for_parsing)
            stage_position = grid_square_data["microscopeData"]["stage"]["Position"]
            tile_id = extractor.get_tile_id(
                (float(stage_position["X"]) * 1e9, float(stage_position["Y"]) * 1e9)
            )
            readout_area = grid_square_data["microscopeData"]["acquisition"]["camera"][
                "ReadoutArea"
            ]
            if tile_id is not None:
                grid_squares.append(
                    GridSquare(
                        grid_square_name=grid_square_dir.name,
                        stage_position_x=float(stage_position["X"]) * 1e9,
                        stage_position_y=float(stage_position["Y"]) * 1e9,
                        thumbnail=str(grid_square_jpeg),
                        pixel_size=float(
                            grid_square_data["SpatialScale"]["pixelSize"]["x"][
                                "numericValue"
                            ]
                        )
                        * 1e9,
                        readout_area_x=int(readout_area["a:width"]),
                        readout_area_y=int(readout_area["a:height"]),
                        tile_id=tile_id,
                    )
                )
            for foil_hole_jpeg in (grid_square_dir / "FoilHoles").glob("FoilHole*.jpg"):
                with open(foil_hole_jpeg.with_suffix(".xml"), "r") as xml:
                    for_parsing = xml.read()
                    foil_hole_data = xmltodict.parse(for_parsing)
                    stage_position = foil_hole_data["microscopeData"]["stage"][
                        "Position"
                    ]
                    readout_area = foil_hole_data["microscopeData"]["acquisition"][
                        "camera"
                    ]["ReadoutArea"]
                    foil_holes.append(
                        FoilHole(
                            grid_square_name=grid_square_dir.name,
                            stage_position_x=float(stage_position["X"]) * 1e9,
                            stage_position_y=float(stage_position["Y"]) * 1e9,
                            thumbnail=str(foil_hole_jpeg),
                            pixel_size=float(
                                foil_hole_data["SpatialScale"]["pixelSize"]["x"][
                                    "numericValue"
                                ]
                            )
                            * 1e9,
                            readout_area_x=int(readout_area["a:width"]),
                            readout_area_y=int(readout_area["a:height"]),
                        )
                    )
