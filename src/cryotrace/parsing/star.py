import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from gemmi import cif

from cryotrace.data_model import ExposureInfo
from cryotrace.data_model.extract import Extractor


def open_star_file(star_file_path: Path):
    gemmi_readable_path = os.fspath(star_file_path)
    return cif.read_file(gemmi_readable_path)


def get_columns(star_file, ignore: Optional[List[str]] = None) -> List[str]:
    json_star = json.loads(star_file.as_json())
    cols = []
    for v in json_star.values():
        if ignore:
            vals = [_v for _v in v.keys() if all(ig not in _v for ig in ignore)]
            cols.extend(vals)
        else:
            cols.extend(v.keys())
    return cols


def get_column_data(star_file, columns: List[str]) -> Dict[str, List[str]]:
    json_star = json.loads(star_file.as_json())
    return {k: v for k, v in json_star.items() if k in columns}


def insert_exposure_data(
    data: Dict[str, List[str]],
    exposure_tag: str,
    star_file_path: str,
    extractor: Extractor,
):
    exposure_info: List[ExposureInfo] = []
    for k, v in data.items():
        if k != exposure_tag:
            for i, value in enumerate(v):
                exinf = ExposureInfo(
                    exposure_name=Path(data[exposure_tag][i]).name.replace(
                        "_Fractions", ""
                    ),
                    source=star_file_path,
                    key=k,
                    value=value,
                )
                exposure_info.append(exinf)
    extractor.put_info(exposure_info)
