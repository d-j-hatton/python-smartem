from pathlib import Path
from typing import Any, Dict, Tuple

import xmltodict

from smartem.data_model import Atlas, Exposure, FoilHole, GridSquare, Tile
from smartem.data_model.extract import DataAPI


def parse_epu_xml(xml_path: Path) -> Dict[str, Any]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["MicroscopeImage"]
    stage_position = data["microscopeData"]["stage"]["Position"]
    readout_area = data["microscopeData"]["acquisition"]["camera"]["ReadoutArea"]
    return {
        "stage_position": (
            float(stage_position["X"]) * 1e9,
            float(stage_position["Y"]) * 1e9,
        ),
        "pixel_size": float(data["SpatialScale"]["pixelSize"]["x"]["numericValue"])
        * 1e9,
        "readout_area": (int(readout_area["a:width"]), int(readout_area["a:height"])),
    }


def parse_epu_xml_version(xml_path: Path) -> Dict[str, Any]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["MicroscopeImage"]
    software = data["microscopeData"]["core"]["ApplicationSoftware"]
    version = data["microscopeData"]["core"]["ApplicationSoftwareVersion"]
    return {
        "software": software,
        "version": version,
    }


def create_atlas_and_tiles(atlas_image: Path, extractor: DataAPI) -> int:
    atlas_data = parse_epu_xml(atlas_image.with_suffix(".xml"))
    atlas = [
        Atlas(
            stage_position_x=atlas_data["stage_position"][0],
            stage_position_y=atlas_data["stage_position"][1],
            thumbnail=str(atlas_image),
            pixel_size=atlas_data["pixel_size"],
            readout_area_x=atlas_data["readout_area"][0],
            readout_area_y=atlas_data["readout_area"][1],
        )
    ]
    extractor.put(atlas)
    atlas_id = atlas[0].atlas_id
    if not atlas_id:
        raise RuntimeError(f"Atlas record was not correctly inserted: {atlas_image}")
    tiles = []
    for tile in atlas_image.parent.glob("Tile_*.jpg"):
        tile_data = parse_epu_xml(tile.with_suffix(".xml"))
        tiles.append(
            Tile(
                atlas_id=atlas_id,
                stage_position_x=tile_data["stage_position"][0],
                stage_position_y=tile_data["stage_position"][1],
                thumbnail=str(tile),
                pixel_size=tile_data["pixel_size"],
                readout_area_x=tile_data["readout_area"][0],
                readout_area_y=tile_data["readout_area"][1],
            )
        )
    extractor.put(tiles)
    return atlas_id


def parse_epu_version(epu_path: Path) -> Tuple[str, str]:
    xml_glob = iter(epu_path.glob("GridSquare*/*.xml"))
    res = parse_epu_xml_version(next(xml_glob))
    return (res["software"], res["version"])


def parse_epu_dir(epu_path: Path, extractor: DataAPI):
    foil_holes: Dict[str, FoilHole] = {}
    exposures = {}
    for grid_square_dir in epu_path.glob("GridSquare*"):
        if grid_square_dir.is_dir():
            grid_square_jpeg = next(grid_square_dir.glob("*.jpg"))
            grid_square_data = parse_epu_xml(grid_square_jpeg.with_suffix(".xml"))
            tile_id = extractor.get_tile_id(grid_square_data["stage_position"])
            if tile_id is not None:
                extractor.put(
                    [
                        GridSquare(
                            grid_square_name=grid_square_dir.name,
                            stage_position_x=grid_square_data["stage_position"][0],
                            stage_position_y=grid_square_data["stage_position"][1],
                            thumbnail=str(grid_square_jpeg.relative_to(epu_path)),
                            pixel_size=grid_square_data["pixel_size"],
                            readout_area_x=grid_square_data["readout_area"][0],
                            readout_area_y=grid_square_data["readout_area"][1],
                            tile_id=tile_id,
                        )
                    ]
                )
            for foil_hole_jpeg in (grid_square_dir / "FoilHoles").glob("FoilHole*.jpg"):
                foil_hole_name = "_".join(foil_hole_jpeg.stem.split("_")[:2])
                if foil_holes.get(foil_hole_name):
                    if (
                        epu_path / foil_holes[foil_hole_name].thumbnail
                    ).stat().st_mtime > foil_hole_jpeg.stat().st_mtime:
                        continue
                foil_hole_data = parse_epu_xml(foil_hole_jpeg.with_suffix(".xml"))
                foil_holes[foil_hole_name] = FoilHole(
                    grid_square_name=grid_square_dir.name,
                    stage_position_x=foil_hole_data["stage_position"][0],
                    stage_position_y=foil_hole_data["stage_position"][1],
                    thumbnail=str(foil_hole_jpeg.relative_to(epu_path)),
                    pixel_size=foil_hole_data["pixel_size"],
                    readout_area_x=foil_hole_data["readout_area"][0],
                    readout_area_y=foil_hole_data["readout_area"][0],
                    foil_hole_name="_".join(foil_hole_jpeg.stem.split("_")[:2]),
                )
            extractor.put(list(foil_holes.values()))
            for exposure_jpeg in (grid_square_dir / "Data").glob("*.jpg"):
                for fh_name in foil_holes.keys():
                    if fh_name in exposure_jpeg.name:
                        foil_hole_name = fh_name
                        break
                else:
                    continue
                exposure_data = parse_epu_xml(exposure_jpeg.with_suffix(".xml"))
                exposures[exposure_jpeg] = Exposure(
                    exposure_name=exposure_jpeg.name,
                    foil_hole_name=foil_hole_name,
                    stage_position_x=exposure_data["stage_position"][0],
                    stage_position_y=exposure_data["stage_position"][1],
                    thumbnail=str(exposure_jpeg.relative_to(epu_path)),
                    pixel_size=exposure_data["pixel_size"],
                    readout_area_x=exposure_data["readout_area"][0],
                    readout_area_y=exposure_data["readout_area"][1],
                )
            extractor.put(list(exposures.values()))
