from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import Load, load_only, sessionmaker

from cryotrace.data_model import (
    Atlas,
    Base,
    EPUImage,
    Exposure,
    ExposureInfo,
    FoilHole,
    GridSquare,
    InfoStore,
    Particle,
    ParticleInfo,
    ParticleSet,
    ParticleSetInfo,
    ParticleSetLinker,
    Project,
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

    def get_projects(self) -> List[str]:
        query = self.session.query(Project).options(load_only("project_name"))
        return [q.project_name for q in query.all()]

    def get_project(self, project_name: str) -> Tuple[Project, Atlas]:
        query = self.session.query(Project).filter(Project.project_name == project_name)
        proj = query.one()
        query = self.session.query(Atlas).filter(Atlas.atlas_id == proj.atlas_id)
        return proj, query.one()

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

    @lru_cache(maxsize=50)
    def get_exposure_names(self, foil_hole_name: str) -> List[str]:
        query = self.session.query(Exposure).filter(
            Exposure.foil_hole_name == foil_hole_name
        )
        return [q.exposure_name for q in query.all()]

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

    def get_particle_set_group_names(self) -> List[str]:
        query = (
            self.session.query(ParticleSet)
            .filter(ParticleSet.atlas_id == self._atlas_id)
            .distinct(ParticleSet.group_name)
        )
        return [q.group_name for q in query.all()]

    def get_particle_info_sources(self) -> List[str]:
        query = (
            self.session.query(
                Tile, GridSquare, FoilHole, Exposure, Particle, ParticleInfo
            )
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(Particle).load_only("exposure_name", "particle_id"), Load(ParticleInfo).load_only("source"))  # type: ignore
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(Tile.atlas_id == self._atlas_id)
            .distinct(ParticleInfo.source)
        )
        return [q[-1].source for q in query.all()]

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
            self.session.query(
                Tile, GridSquare, FoilHole, Exposure, Particle, ParticleInfo
            )
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(Particle).load_only("exposure_name", "particle_id"), Load(ParticleInfo).load_only("key"))  # type: ignore
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(Tile.atlas_id == self._atlas_id)
            .distinct(ParticleInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_all_particle_set_keys(self) -> List[str]:
        query = (
            self.session.query(ParticleSet, ParticleSetInfo)
            .options(Load(ParticleSet).load_only("atlas_id", "identifier"), Load(ParticleSetInfo).load_only("key"))  # type: ignore
            .join(ParticleSet, ParticleSet.identifier == ParticleSetInfo.set_name)
            .filter(ParticleSet.atlas_id == self._atlas_id)
            .distinct(ParticleSetInfo.key)
        )
        return [q[-1].key for q in query.all()]

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

    def get_particles(self, exposure_name: str) -> List[Particle]:
        query = self.session.query(Particle).filter(
            Particle.exposure_name == exposure_name
        )
        return query.all()

    def get_particle_id(self, exposure_name: str, x: float, y: float) -> Optional[int]:
        query = self.session.query(Particle).filter(
            Particle.exposure_name == exposure_name, Particle.x == x, Particle.y == y
        )
        _particle = query.all()
        if not _particle:
            return None
        if len(_particle) > 1:
            raise ValueError(
                f"More than one particle found for exposure [{exposure_name}], x [{x}], y [{y}]"
            )
        particle = _particle[0]
        return particle.particle_id

    def put_particle(self, exposure_name: str, x: float, y: float) -> int:
        particle = Particle(exposure_name=exposure_name, x=x, y=y)
        self.session.add(particle)
        self.session.commit()
        return particle.particle_id

    def put_particles(self, particles: List[Particle]):
        for p in particles:
            self.session.add(p)
        self.session.commit()

    def put_info(self, info: Sequence[InfoStore]):
        for i in info:
            self.session.add(i)
        self.session.commit()

    def put(self, entries: Sequence[Base]):
        for entry in entries:
            self.session.add(entry)
        self.session.commit()

    def get_exposure_stats(self, exposure_name: str, key: str) -> List[float]:
        query = (
            self.session.query(Particle, ParticleInfo)
            .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
            .filter(ParticleInfo.key == key)
            .filter(Particle.exposure_name == exposure_name)
        )
        values = [q[-1].value for q in query.all()]
        return values

    def get_exposure_stats_multi(
        self, exposure_name: str, keys: List[str]
    ) -> Dict[str, List[float]]:
        stats: Dict[str, List[float]] = {}
        if not keys:
            return stats
        query = (
            self.session.query(Particle, ParticleInfo)
            .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
            .filter(ParticleInfo.key.in_(keys))
            .filter(Particle.exposure_name == exposure_name)
        )
        info = [q[-1] for q in query.all()]
        for key in keys:
            stats[key] = [q.value for q in info if q.key == key]
        return stats

    def get_exposure_stats_particle_set(
        self, exposure_name: str, key: str
    ) -> List[float]:
        query = (
            self.session.query(Particle, ParticleSetLinker, ParticleSetInfo)
            .join(Particle, Particle.particle_id == ParticleSetLinker.particle_id)
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key == key)
            .filter(Particle.exposure_name == exposure_name)
        )
        values = [q[-1].value for q in query.all()]
        return values

    def get_exposure_stats_particle_set_multi(
        self, exposure_name: str, keys: List[str]
    ) -> Dict[str, List[float]]:
        stats: Dict[str, List[float]] = {}
        if not keys:
            return stats
        query = (
            self.session.query(Particle, ParticleSetLinker, ParticleSetInfo)
            .join(Particle, Particle.particle_id == ParticleSetLinker.particle_id)
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(keys))
            .filter(Particle.exposure_name == exposure_name)
        )
        info = [q[-1] for q in query.all()]
        for key in keys:
            stats[key] = [q.value for q in info if q.key == key]
        return stats

    def get_foil_hole_stats_all(
        self,
        foil_hole_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, List[float]]:
        stats: Dict[str, List[float]] = {}
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return stats
        exposures = self.get_exposure_names(foil_hole_name)
        exposure_query = (
            self.session.query(Exposure, ExposureInfo)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .filter(ExposureInfo.key.in_(exposure_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
        )
        particle_query = (
            self.session.query(Exposure, Particle, ParticleInfo)
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
        )
        particle_set_query = (
            self.session.query(Exposure, Particle, ParticleSetLinker, ParticleSetInfo)
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
        )
        exposure_results = exposure_query.all()
        particle_results = particle_query.all()
        particle_set_results = particle_set_query.all()
        for k in exposure_keys:
            stats[k] = []
            for exp in exposures:
                stats[k].extend(
                    er[-1].value
                    for er in exposure_results
                    if er[-1].key == k and er[0].exposure_name == exp
                )
        for k in particle_keys:
            stats[k] = []
            for exp in exposures:
                if avg_particles:
                    stats[k].append(
                        np.mean(
                            [
                                er[-1].value
                                for er in particle_results
                                if er[-1].key == k and er[0].exposure_name == exp
                            ]
                        )
                    )
                else:
                    stats[k].extend(
                        er[-1].value
                        for er in particle_results
                        if er[-1].key == k and er[0].exposure_name == exp
                    )
        for k in particle_set_keys:
            stats[k] = []
            for exp in exposures:
                if avg_particles:
                    stats[k].append(
                        np.mean(
                            [
                                er[-1].value
                                for er in particle_set_results
                                if er[-1].key == k and er[0].exposure_name == exp
                            ]
                        )
                    )
                else:
                    stats[k].extend(
                        er[-1].value
                        for er in particle_set_results
                        if er[-1].key == k and er[0].exposure_name == exp
                    )
        return stats

    def get_grid_square_stats_all(
        self,
        grid_square_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, Dict[str, List[float]]]:
        stats: Dict[str, Dict[str, List[float]]] = {}
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return stats
        foil_holes = self.get_foil_holes(grid_square_name)
        for fh in foil_holes:
            fh_stats = self.get_foil_hole_stats_all(
                fh.foil_hole_name,
                exposure_keys,
                particle_keys,
                particle_set_keys,
                avg_particles=avg_particles,
            )
            for k, v in fh_stats.items():
                try:
                    stats[k].update({fh.foil_hole_name: v})
                except KeyError:
                    stats[k] = {fh.foil_hole_name: v}
        return stats

    def get_atlas_stats(
        self,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, Dict[str, List[float]]]:
        stats: Dict[str, Dict[str, List[float]]] = {}
        grid_squares = self.get_grid_squares()
        for k in exposure_keys + particle_keys + particle_set_keys:
            stats[k] = {}
        for gs in grid_squares:
            foil_holes = self.get_foil_holes(gs.grid_square_name)
            gs_data = self.get_grid_square_stats_all(
                gs.grid_square_name,
                exposure_keys,
                particle_keys,
                particle_set_keys,
                avg_particles=avg_particles,
            )
            for k in gs_data.keys():
                stats[k][gs.grid_square_name] = []
                for fh in foil_holes:
                    stats[k][gs.grid_square_name].extend(gs_data[k][fh.foil_hole_name])
        return stats
