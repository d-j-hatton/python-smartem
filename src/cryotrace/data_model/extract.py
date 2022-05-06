from functools import lru_cache
from typing import List, Optional, Sequence, Tuple, Union

from sqlalchemy import and_, create_engine
from sqlalchemy.orm import Load, load_only, sessionmaker

from cryotrace.data_model import (
    Atlas,
    EPUImage,
    Exposure,
    ExposureInfo,
    FoilHole,
    GridSquare,
    InfoStore,
    Particle,
    ParticleInfo,
    Tile,
    url,
)


class Extractor:
    def __init__(self, atlas_id: int = 0):
        _url = url()
        self._atlas_id = atlas_id
        self.engine = create_engine(_url)
        self.session = sessionmaker(bind=self.engine)()

    # @lru_cache(maxsize=1)
    def get_atlas(self) -> Optional[Atlas]:
        query = self.session.query(Atlas).filter(Atlas.atlas_id == self._atlas_id)
        try:
            return query.all()[0]
        except IndexError:
            return None

    def get_atlases(self) -> List[str]:
        query = self.session.query(Atlas).options(load_only("thumbnail"))
        return [q.thumbnail for q in query.all()]

    def get_grid_squares(self) -> List[GridSquare]:
        query = (
            self.session.query(Tile, GridSquare)
            .options(Load(Tile).load_only("tile_id", "atlas_id"))  # type: ignore
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .filter(Tile.atlas_id == self._atlas_id)
        )
        return [q[1] for q in query.all()]

    def get_all_exposures(self) -> List[Exposure]:
        query = (
            self.session.query(Tile, GridSquare, FoilHole, Exposure)
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"))  # type: ignore
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .filter(Tile.atlas_id == self._atlas_id)
        )
        return [q[-1] for q in query.all()]

    @lru_cache(maxsize=50)
    def get_foil_holes(self, grid_square_name: str) -> List[FoilHole]:
        query = self.session.query(FoilHole).filter(
            FoilHole.grid_square_name == grid_square_name
        )
        return query.all()

    @lru_cache(maxsize=50)
    def get_exposures(self, foil_hole_name: str) -> List[Exposure]:
        query = self.session.query(Exposure).filter(
            Exposure.foil_hole_name == foil_hole_name
        )
        return query.all()

    def set_atlas_id(self, atlas_path: str) -> bool:
        query = self.session.query(Atlas).options(load_only("thumbnail", "atlas_id"))
        for q in query.all():
            if q.thumbnail == atlas_path:
                self._atlas_id = q.atlas_id
                return True
        return False

    def get_tile(self, stage_position: Tuple[float, float]) -> Optional[Tile]:
        query = self.session.query(Tile).filter(Tile.atlas_id == self._atlas_id)
        tiles = query.all()
        for tile in tiles:
            left = tile.stage_position_x - 0.5 * (tile.pixel_size * tile.readout_area_x)
            right = tile.stage_position_x + 0.5 * (
                tile.pixel_size * tile.readout_area_x
            )
            top = tile.stage_position_y + 0.5 * (tile.pixel_size * tile.readout_area_y)
            bottom = tile.stage_position_y - 0.5 * (
                tile.pixel_size * tile.readout_area_y
            )
            if stage_position[0] > left and stage_position[0] < right:
                if stage_position[1] < top and stage_position[1] > bottom:
                    return tile
        return None

    def get_tile_id(self, stage_position: Tuple[float, float]) -> Optional[int]:
        tile = self.get_tile(stage_position)
        if tile:
            return tile.tile_id
        return None

    def get_all_exposure_keys(self) -> List[str]:
        query = (
            self.session.query(Tile, GridSquare, FoilHole, Exposure, ExposureInfo)
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(ExposureInfo).load_only("key"))  # type: ignore
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(ExposureInfo, ExposureInfo.exposure_name == Exposure.exposure_name)
            .filter(Tile.atlas_id == self._atlas_id)
            .distinct(ExposureInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_all_particle_keys(self) -> List[str]:
        query = (
            self.session.query(ParticleInfo)
            .options(Load(ParticleInfo).load_only("key"))  # type: ignore
            .distinct(ParticleInfo.key)
        )
        return [q.key for q in query.all()]

    def put_image_data(
        self, images: Sequence[EPUImage], return_key: Optional[str] = None
    ) -> Optional[List[Union[str, int]]]:
        for im in images:
            self.session.add(im)
        self.session.commit()
        if return_key:
            return [getattr(im, return_key) for im in images]
        else:
            return None

    def get_particle_id(self, exposure_name: str, x: float, y: float) -> int:
        query = self.session.query(Exposure).filter(
            Particle.exposure_name == exposure_name, Particle.x == x, Particle.y == y
        )
        _particle = query.all()
        if not _particle:
            raise ValueError(
                f"No exposure found for exposure [{exposure_name}], x [{x}], y [{y}]"
            )
        if len(_particle) > 1:
            raise ValueError(
                f"More than one exposure found for exposure [{exposure_name}], x [{x}], y [{y}]"
            )
        particle = _particle[0]
        return particle.particle_id

    def put_info(self, info: Sequence[InfoStore]):
        for i in info:
            self.session.add(i)
        self.session.commit()

    def get_grid_square_data(
        self, grid_square_name: str, keys: Optional[List[str]] = None
    ) -> list:
        if not keys:
            query = (
                self.session.query(
                    FoilHole, Exposure, Particle, ParticleInfo, ExposureInfo
                )
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
                .filter(FoilHole.grid_square_name == grid_square_name)
            )
        else:
            query = (
                self.session.query(
                    FoilHole, Exposure, Particle, ParticleInfo, ExposureInfo
                )
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
                .filter(FoilHole.grid_square_name == grid_square_name)
                .filter(ExposureInfo.key.in_(keys))
                .filter(ParticleInfo.key.in_(keys))
            )
        return query.all()

    def get_foil_hole_data(
        self, foil_hole_name: str, keys: Optional[List[str]] = None
    ) -> list:
        if not keys:
            query = (
                self.session.query(Exposure, Particle, ParticleInfo, ExposureInfo)
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .filter(Exposure.foil_hole_name == foil_hole_name)
            )
        else:
            query = (
                self.session.query(Exposure, Particle, ParticleInfo, ExposureInfo)
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .filter(Exposure.foil_hole_name == foil_hole_name)
                .filter(ExposureInfo.key.in_(keys))
                .filter(ParticleInfo.key.in_(keys))
            )
        return query.all()

    def get_exposure_data(
        self, exposure_name: str, keys: Optional[List[str]] = None
    ) -> list:
        if not keys:
            query = (
                self.session.query(Exposure, Particle, ParticleInfo, ExposureInfo)
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .filter(Exposure.exposure_name == exposure_name)
            )
        else:
            query = (
                self.session.query(Exposure, Particle, ParticleInfo, ExposureInfo)
                .join(
                    Exposure,
                    and_(
                        Exposure.exposure_name == ExposureInfo.exposure_name,
                        Exposure.exposure_name == Particle.exposure_name,
                    ),
                )
                .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
                .filter(Exposure.exposure_name == exposure_name)
                .filter(ExposureInfo.key.in_(keys))
                .filter(ParticleInfo.key.in_(keys))
            )
        return query.all()

    def get_foil_hole_stats(self, foil_hole_name: str, key: str) -> List[float]:
        query = (
            self.session.query(Exposure, ExposureInfo)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .filter(ExposureInfo.key == key)
            .filter(Exposure.foil_hole_name == foil_hole_name)
        )
        values = [q[-1].value for q in query.all()]
        return values
