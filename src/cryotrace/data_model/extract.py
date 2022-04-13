import os
from pathlib import Path
from typing import List, Optional, Union

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cryotrace.data_model import (
    Exposure,
    ExposureInfo,
    FoilHole,
    Particle,
    ParticleInfo,
)


def url(credentials_file: Optional[Union[str, Path]] = None) -> str:
    if not credentials_file:
        credentials_file = os.getenv("CRYOTRACE_CREDENTIALS")

    if not credentials_file:
        raise AttributeError(
            "No credentials file specified for cryotrace database (environment variable CRYOTRACE_CREDENTIALS)"
        )

    with open(credentials_file, "r") as stream:
        creds = yaml.safe_load(stream)

    return f"postgresql+psycopg2://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['database']}"


class Extractor:
    def __init__(self):
        _url = url()
        self.engine = create_engine(_url)
        self.session = sessionmaker(bind=self.engine)()

    def get_for_grid_square(
        self, grid_square_name: str, keys: Optional[List[str]] = None
    ) -> list:
        res = []
        if not keys:
            query = (
                self.session.query(
                    FoilHole, Exposure, Particle, ParticleInfo, ExposureInfo
                )
                .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
                .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
                .filter(FoilHole.grid_square_name == grid_square_name)
            )
            res = query.all()
        return res
