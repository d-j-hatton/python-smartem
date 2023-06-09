from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import xmltodict

from smartem.data_model import Atlas, Exposure, FoilHole, GridSquare, Tile
from smartem.data_model.extract import DataAPI
from smartem.stage_model import StageCalibration, calibrate


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


def metadata_grid_square_positions(xml_path: Path) -> Dict[str, Tuple[int, int]]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    tile_info = data["AtlasSessionXml"]["Atlas"]["TilesEfficient"]["_items"]["TileXml"]
    gs_pix_positions = {}
    for ti in tile_info:
        try:
            nodes = ti["Nodes"]["KeyValuePairs"]
        except KeyError:
            continue
        required_key = ""
        for key in nodes.keys():
            if key.startswith("KeyValuePairOfintNodeXml"):
                required_key = key
                break
        if not required_key:
            continue
        for gs in nodes[required_key]:
            gs_pix_positions[gs["key"]] = (
                int(float(gs["value"]["b:PositionOnTheAtlas"]["c:Center"]["d:x"])),
                int(float(gs["value"]["b:PositionOnTheAtlas"]["c:Center"]["d:y"])),
            )
    return gs_pix_positions


def metadata_grid_square_stage(xml_path: Path) -> Dict[str, Tuple[float, float]]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    tile_info = data["AtlasSessionXml"]["Atlas"]["TilesEfficient"]["_items"]["TileXml"]
    gs_stage_positions = {}
    for ti in tile_info:
        try:
            nodes = ti["Nodes"]["KeyValuePairs"]
        except KeyError:
            continue
        required_key = ""
        for key in nodes.keys():
            if key.startswith("KeyValuePairOfintNodeXml"):
                required_key = key
                break
        if not required_key:
            continue
        for gs in nodes[required_key]:
            gs_stage_positions[gs["key"]] = (
                float(gs["value"]["b:PositionOnTheAtlas"]["c:Physical"]["d:x"]) * 1e9,
                float(gs["value"]["b:PositionOnTheAtlas"]["c:Physical"]["d:y"]) * 1e9,
            )
    return gs_stage_positions


def mask_foil_hole_positions(
    xml_path: Path, image_size: Tuple[int, int], diameter: float | None = None
):
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["GridSquareXml"]
    serialization_array = data["TargetLocations"]["TargetLocationsEfficient"][
        "a:m_serializationArray"
    ]
    required_key = ""
    for key in serialization_array.keys():
        if key.startswith("b:KeyValuePairOfintTargetLocation"):
            required_key = key
            break
    if not required_key:
        return {}
    fh_pix_positions = {}
    for fh_block in serialization_array[required_key]:
        if fh_block["b:value"]["IsNearGridBar"] == "false":
            pix_center = fh_block["b:value"]["PixelCenter"]
            fh_pix_positions[fh_block["b:key"]] = (
                int(float(pix_center["c:x"])),
                int(float(pix_center["c:y"])),
            )
            if not diameter:
                diameter = float(fh_block["b:value"]["PixelWidthHeight"]["c:height"])

    mask = np.full(image_size, False)
    if not diameter:
        return mask
    for fh in fh_pix_positions.values():
        for yidx in range(int(fh[1] - diameter / 2), fh[1] + 1):
            xidx = fh[0]
            yshift = -(fh[1] - yidx)
            while (yidx - fh[1]) ** 2 + (xidx - fh[0]) ** 2 <= (diameter / 2) ** 2:
                xshift = xidx - fh[0]
                try:
                    mask[xidx][yidx] = True
                    mask[xidx][fh[1] - yshift] = True
                    mask[fh[0] - xshift][fh[1] - yshift] = True
                    mask[fh[0] - xshift][yidx] = True
                except IndexError:
                    pass
                xidx += 1
    return mask.transpose()


def metadata_foil_hole_positions(xml_path: Path) -> Dict[str, Tuple[int, int]]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["GridSquareXml"]
    serialization_array = data["TargetLocations"]["TargetLocationsEfficient"][
        "a:m_serializationArray"
    ]
    required_key = ""
    for key in serialization_array.keys():
        if key.startswith("b:KeyValuePairOfintTargetLocation"):
            required_key = key
            break
    if not required_key:
        return {}
    fh_stage_positions = {}
    for fh_block in serialization_array[required_key]:
        if fh_block["b:value"]["IsNearGridBar"] == "false":
            stage = fh_block["b:value"]["PixelCenter"]
            fh_stage_positions[fh_block["b:key"]] = (
                int(float(stage["c:x"])),
                int(float(stage["c:y"])),
            )
    return fh_stage_positions


def metadata_foil_hole_stage(xml_path: Path) -> Dict[str, Tuple[float, float]]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["GridSquareXml"]
    serialization_array = data["TargetLocations"]["TargetLocationsEfficient"][
        "a:m_serializationArray"
    ]
    required_key = ""
    for key in serialization_array.keys():
        if key.startswith("b:KeyValuePairOfintTargetLocation"):
            required_key = key
            break
    if not required_key:
        return {}
    fh_stage_positions = {}
    for fh_block in serialization_array[required_key]:
        if fh_block["b:value"]["IsNearGridBar"] == "false":
            stage = fh_block["b:value"]["StagePosition"]
            fh_stage_positions[fh_block["b:key"]] = (
                float(stage["c:X"]) * 1e9,
                float(stage["c:Y"]) * 1e9,
            )
    return fh_stage_positions


def metadata_foil_hole_corrected_stage(
    xml_path: Path,
) -> Dict[str, tuple]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["GridSquareXml"]
    serialization_array = data["TargetLocations"]["TargetLocationsEfficient"][
        "a:m_serializationArray"
    ]
    required_key = ""
    for key in serialization_array.keys():
        if key.startswith("b:KeyValuePairOfintTargetLocation"):
            required_key = key
            break
    if not required_key:
        return {}
    fh_cs_positions: Dict[str, tuple] = {}
    for fh_block in serialization_array[required_key]:
        if fh_block["b:value"]["IsPositionCorrected"] == "true":
            corrected_stage = fh_block["b:value"]["CorrectedStagePosition"]
            fh_cs_positions[fh_block["b:key"]] = (
                float(corrected_stage["c:X"]) * 1e9,
                float(corrected_stage["c:Y"]) * 1e9,
            )
        else:
            fh_cs_positions[fh_block["b:key"]] = (None, None)
    return fh_cs_positions


def calibrate_coordinate_system(xml_path: Path) -> Optional[StageCalibration]:
    with open(xml_path, "r") as xml:
        for_parsing = xml.read()
        data = xmltodict.parse(for_parsing)
    data = data["GridSquareXml"]
    serialization_array = data["TargetLocations"]["TargetLocationsEfficient"][
        "a:m_serializationArray"
    ]
    required_key = ""
    for key in serialization_array.keys():
        if key.startswith("b:KeyValuePairOfintTargetLocation"):
            required_key = key
            break
    if not required_key:
        return None
    found = False
    for i in range(len(serialization_array[required_key]) - 1):
        pix_positions = (
            (
                int(
                    float(
                        serialization_array[required_key][i]["b:value"]["PixelCenter"][
                            "c:x"
                        ]
                    )
                ),
                int(
                    float(
                        serialization_array[required_key][i]["b:value"]["PixelCenter"][
                            "c:y"
                        ]
                    )
                ),
            ),
            (
                int(
                    float(
                        serialization_array[required_key][
                            (i + 10) % len(serialization_array[required_key])
                        ]["b:value"]["PixelCenter"]["c:x"]
                    )
                ),
                int(
                    float(
                        serialization_array[required_key][
                            (i + 10) % len(serialization_array[required_key])
                        ]["b:value"]["PixelCenter"]["c:y"]
                    )
                ),
            ),
        )
        if (
            serialization_array[required_key][i]["b:value"]["IsPositionCorrected"]
            == "true"
        ):
            phys_01 = (
                float(
                    serialization_array[required_key][i]["b:value"][
                        "CorrectedStagePosition"
                    ]["c:X"]
                ),
                float(
                    serialization_array[required_key][i]["b:value"][
                        "CorrectedStagePosition"
                    ]["c:Y"]
                ),
            )
        else:
            phys_01 = (
                float(
                    serialization_array[required_key][i]["b:value"]["StagePosition"][
                        "c:X"
                    ]
                ),
                float(
                    serialization_array[required_key][i]["b:value"]["StagePosition"][
                        "c:Y"
                    ]
                ),
            )
        if (
            serialization_array[required_key][
                (i + 10) % len(serialization_array[required_key])
            ]["b:value"]["IsPositionCorrected"]
            == "true"
        ):
            phys_02 = (
                float(
                    serialization_array[required_key][
                        (i + 10) % len(serialization_array[required_key])
                    ]["b:value"]["CorrectedStagePosition"]["c:X"]
                ),
                float(
                    serialization_array[required_key][
                        (i + 10) % len(serialization_array[required_key])
                    ]["b:value"]["CorrectedStagePosition"]["c:Y"]
                ),
            )
        else:
            phys_02 = (
                float(
                    serialization_array[required_key][
                        (i + 10) % len(serialization_array[required_key])
                    ]["b:value"]["StagePosition"]["c:X"]
                ),
                float(
                    serialization_array[required_key][
                        (i + 10) % len(serialization_array[required_key])
                    ]["b:value"]["StagePosition"]["c:Y"]
                ),
            )
        physical_positions = (phys_01, phys_02)
        pix_diff = (
            pix_positions[1][0] - pix_positions[0][0],
            pix_positions[1][1] - pix_positions[0][1],
        )
        physical_diff = (
            physical_positions[1][0] - physical_positions[0][0],
            physical_positions[1][1] - physical_positions[0][1],
        )
        if (
            all(physical_diff)
            and all(pix_diff)
            and pix_diff[0] > 100
            and pix_diff[1] > 100
        ):
            found = True
            break
    if not found:
        return None
    return calibrate(pix_positions, physical_positions)


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
    pid = extractor.put(atlas)
    atlas_id = pid[0].atlas_id  # atlas[0].atlas_id
    if atlas_id is None:
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


def parse_epu_dir(epu_path: Path, atlas_path: Path, extractor: DataAPI, project: str):
    exposures = {}
    for grid_square_dir in epu_path.glob("GridSquare*"):
        if grid_square_dir.is_dir():
            foil_holes: Dict[str, FoilHole] = {}
            afis_foil_holes: Dict[str, FoilHole] = {}
            grid_square_jpeg = next(grid_square_dir.glob("*.jpg"))
            grid_square_data = parse_epu_xml(grid_square_jpeg.with_suffix(".xml"))
            # grid_square_label = grid_square_dir.name.split("_")[1]
            metadata_path = epu_path.parent / "Metadata"
            foil_hole_stage = metadata_foil_hole_stage(
                metadata_path / f"{grid_square_dir.name}.dm"
            )
            # grid_square_stage = metadata_grid_square_stage(
            #     atlas_path / "Atlas.dm"
            # )
            tile_id = extractor.get_tile_id(grid_square_data["stage_position"], project)
            print(tile_id)
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
            else:
                continue
            for foil_hole_jpeg in (grid_square_dir / "FoilHoles").glob("FoilHole*.jpg"):
                foil_hole_name = "_".join(foil_hole_jpeg.stem.split("_")[:2])
                if foil_holes.get(foil_hole_name):
                    thumbnail = foil_holes[foil_hole_name].thumbnail
                    if thumbnail:
                        if (
                            epu_path / thumbnail
                        ).stat().st_mtime > foil_hole_jpeg.stat().st_mtime:
                            continue
                foil_hole_data = parse_epu_xml(foil_hole_jpeg.with_suffix(".xml"))
                foil_hole_label = foil_hole_name.split("_")[1]
                foil_holes[foil_hole_name] = FoilHole(
                    grid_square_name=grid_square_dir.name,
                    stage_position_x=foil_hole_data["stage_position"][0],
                    stage_position_y=foil_hole_data["stage_position"][1],
                    thumbnail=str(foil_hole_jpeg.relative_to(epu_path)),
                    pixel_size=foil_hole_data["pixel_size"],
                    readout_area_x=foil_hole_data["readout_area"][0],
                    readout_area_y=foil_hole_data["readout_area"][0],
                    foil_hole_name=foil_hole_name,
                    adjusted_stage_position_x=foil_hole_stage[foil_hole_label][0],
                    adjusted_stage_position_y=foil_hole_stage[foil_hole_label][1],
                )
            extractor.put(list(foil_holes.values()))
            for exposure_jpeg in (grid_square_dir / "Data").glob("*.jpg"):
                exposure_data = parse_epu_xml(exposure_jpeg.with_suffix(".xml"))
                for fh_name in foil_holes.keys():
                    if fh_name in exposure_jpeg.name:
                        foil_hole_name = fh_name
                        break
                else:
                    foil_hole_name = exposure_jpeg.name.split("_Data")[0]
                    foil_hole_label = foil_hole_name.split("_")[1]
                    adjusted_stage_position = foil_hole_stage[foil_hole_label]
                    afis_foil_holes[foil_hole_name] = FoilHole(
                        grid_square_name=grid_square_dir.name,
                        stage_position_x=exposure_data["stage_position"][0],
                        stage_position_y=exposure_data["stage_position"][1],
                        thumbnail=None,
                        pixel_size=None,
                        readout_area_x=None,
                        readout_area_y=None,
                        foil_hole_name=foil_hole_name,
                        adjusted_stage_position_x=adjusted_stage_position[0],
                        adjusted_stage_position_y=adjusted_stage_position[1],
                    )
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
            extractor.put(list(afis_foil_holes.values()))
            extractor.put(list(exposures.values()))
