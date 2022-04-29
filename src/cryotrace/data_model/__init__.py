import os
from pathlib import Path
from typing import Any, Optional, Type, Union, cast

import yaml
from sqlalchemy import Column
from sqlalchemy import Float as Float_org
from sqlalchemy import ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql.type_api import TypeEngine

# this is a mypy workaround suggeted in https://github.com/dropbox/sqlalchemy-stubs/issues/178
Float = cast(Type[TypeEngine[float]], Float_org)

Base: Any = declarative_base()


class EPUImage:
    stage_position_x: Column = Column(
        Float,
        comment="x postion of the microscope stage [nm]",
        nullable=False,
    )

    stage_position_y: Column = Column(
        Float,
        comment="y postion of the microscope stage [nm]",
        nullable=False,
    )

    thumbnail = Column(
        String(250),
        nullable=False,
        comment="Full path to EPU jpeg image of EPU image",
    )

    pixel_size: Column = Column(
        Float,
        nullable=False,
        comment="Pixel size of full readout image extracted from EPU XML [nm]",
    )

    readout_area_x = Column(
        Integer,
        nullable=False,
        comment="x-extent of detector readout area",
    )

    readout_area_y = Column(
        Integer,
        nullable=False,
        comment="y-extent of detector readout area",
    )


class Atlas(EPUImage, Base):
    __tablename__ = "Atlas"

    atlas_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )


class Tile(EPUImage, Base):
    __tablename__ = "Tile"

    tile_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    atlas_id: Column = Column(ForeignKey("Atlas.atlas_id"), index=True)
    Atlas = relationship("Atlas")


class GridSquare(EPUImage, Base):
    __tablename__ = "GridSquare"

    grid_square_name = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    tile_id: Column = Column(ForeignKey("Tile.tile_id"), index=True)
    Tile = relationship("Tile")


class FoilHole(EPUImage, Base):
    __tablename__ = "FoilHole"

    foil_hole_name = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    grid_square_name: Column = Column(
        ForeignKey("GridSquare.grid_square_name"), index=True
    )
    GridSquare = relationship("GridSquare")


class Exposure(EPUImage, Base):
    __tablename__ = "Exposure"

    exposure_name = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    foil_hole_name: Column = Column(ForeignKey("FoilHole.foil_hole_name"), index=True)
    FoilHole = relationship("FoilHole")


class Particle(Base):
    __tablename__ = "Particle"

    particle_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    x: Column = Column(
        Float,
        nullable=False,
    )

    y: Column = Column(
        Float,
        nullable=False,
    )

    exposure_name: Column = Column(ForeignKey("Exposure.exposure_name"), index=True)
    Exposure = relationship("Exposure")


class ParticleInfo(Base):
    __tablename__ = "ParticleInfo"

    source = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    key = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    value: Column = Column(
        Float,
        primary_key=True,
        nullable=False,
    )

    particle_id: Column = Column(
        ForeignKey("Particle.particle_id"), primary_key=True, index=True
    )
    Particle = relationship("Particle")


class ExposureInfo(Base):
    __tablename__ = "ExposureInfo"

    source = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    key = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    value: Column = Column(
        Float,
        primary_key=True,
        nullable=False,
    )

    exposure_name: Column = Column(
        ForeignKey("Exposure.exposure_name"), primary_key=True, index=True
    )
    Exposure = relationship("Exposure")


class ParticleSet(Base):
    __tablename__ = "ParticleSet"

    name = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    size = Column(
        Integer,
        nullable=False,
    )


class ParticleSetLinker(Base):
    __tablename__ = "ParticleSetLinker"

    particle_id: Column = Column(
        ForeignKey("Particle.particle_id"), primary_key=True, index=True
    )
    Particle = relationship("Particle")

    set_name: Column = Column(ForeignKey("ParticleSet.name"), primary_key=True)
    ParticleSet = relationship("ParticleSet")


_tables = [
    Atlas,
    Tile,
    GridSquare,
    FoilHole,
    Exposure,
    Particle,
    ParticleInfo,
    ExposureInfo,
]


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


def setup():
    engine = create_engine(url())
    for tab in _tables:
        tab.__table__.create(engine)


def teardown():
    engine = create_engine(url())
    for tab in _tables[::-1]:
        tab.__table__.drop(engine)
