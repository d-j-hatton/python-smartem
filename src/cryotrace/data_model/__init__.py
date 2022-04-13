from typing import Any

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.ext.declaritive import declarative_base
from sqlalchemy.orm import relationship

Base: Any = declarative_base()


class EPUImage(Base):
    stage_position_x = Column(
        Float,
        comment="x postion of the microscope stage [nm]",
        nullable=False,
    )

    stage_position_y = Column(
        Float,
        comment="y postion of the microscope stage [nm]",
        nullable=False,
    )

    thumbnail = Column(
        String(250),
        nullable=False,
        comment="Full path to EPU jpeg image of EPU image",
    )

    pixel_size = Column(
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


class Atlas(EPUImage):
    __tablename__ = "Atlas"

    atlas_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )


class Tile(EPUImage):
    __tablename__ = "Tile"

    tile_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        nullable=False,
    )

    atlas_id: Column = Column(ForeignKey("Atlas.atlas_id"), index=True)
    Atlas = relationship("Atlas")


class GridSquare(EPUImage):
    __tablename__ = "GridSquare"

    grid_square_name = Column(
        String,
        primary_key=True,
        nullable=False,
    )

    tile_id: Column = Column(ForeignKey("Tile.tile_id"), index=True)
    Tile = relationship("Tile")


class FoilHole(EPUImage):
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


class Exposure(EPUImage):
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

    x = Column(
        Float,
        nullable=False,
    )

    y = Column(
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

    value = Column(
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

    value = Column(
        Float,
        primary_key=True,
        nullable=False,
    )

    exposure_name: Column = Column(
        ForeignKey("Exposure.exposure_name"), primary_key=True, index=True
    )
    Exposure = relationship("Exposure")
