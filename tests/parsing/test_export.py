import pytest
from unittest.mock import MagicMock

import xml.etree.ElementTree as ET

#from smartem.parsing import export


class SampleAtlas:
    pass

def test_get_dataframe():
    DataAPI = MagicMock()
    DataAPI.get_grid_squares["test_project"] = [0, 1]
    DataAPI.get_foil_holes["test_project"] = [2, 3]
    DataAPI.get_project["api_project"] = ["test_project"]
    DataAPI.get_atlas_from_project["api_project"] = [{"atlas_id": 0}]

    #return_value = export.get_dataframe(DataAPI, ["test_project"])