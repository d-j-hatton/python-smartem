from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, Union

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
from cryotrace.data_model.construct import linear_joins, table_chain


class DataAPI:
    def __init__(self, project: str = ""):
        _url = url()
        self._project = project
        engine = create_engine(_url)
        self.session = sessionmaker(bind=engine)()

    def set_project(self, project: str) -> bool:
        self._project = project
        return project in self.get_projects()

    def get_project(self, project_name: str = "") -> Project:
        if project_name:
            query = (
                self.session.query(Project)
                .options(load_only("project_name"))
                .filter(Project.project_name == project_name)
            )
        else:
            query = (
                self.session.query(Project)
                .options(load_only("project_name"))
                .filter(Project.project_name == self._project)
            )
        return query.all()[0]

    def get_projects(self) -> List[str]:
        query = self.session.query(Project).options(load_only("project_name"))
        return [q.project_name for q in query.all()]

    def get_atlas_from_project(self, project: Project) -> Atlas:
        query = (
            self.session.query(Project, Atlas)
            .join(Project, Project.atlas_id == Atlas.atlas_id)
            .filter(Project.project_name == project.project_name)
        )
        atlases = [q[1] for q in query.all()]
        return atlases[0]

    def get_atlases(self) -> Union[Atlas, List[Atlas]]:
        if self._project:
            query = (
                self.session.query(Project, Atlas)
                .join(Project, Project.atlas_id == Atlas.atlas_id)
                .filter(Project.project_name == self._project)
            )
            atlases = [q[1] for q in query.all()]
            if len(atlases) == 1:
                return atlases[0]
            return atlases
        return []

    def get_tile(
        self, stage_position: Tuple[float, float], atlas_id: Optional[int] = None
    ) -> Optional[Tile]:
        if atlas_id is None:
            atlas = self.get_atlases()
            if not atlas or isinstance(atlas, list):
                return None
            atlas_id = atlas.atlas_id
        query = self.session.query(Tile).filter(Tile.atlas_id == atlas_id)
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

    def get_grid_squares(
        self, atlas_id: Optional[int] = None, tile_id: Optional[int] = None
    ) -> List[GridSquare]:
        if self._project:
            primary_filter: Any = None
            end: Type[Base] = Tile
            if tile_id is not None:
                end = GridSquare
                primary_filter = tile_id
            elif atlas_id is not None:
                primary_filter = atlas_id
            tables = table_chain(GridSquare, end)
            if primary_filter is None:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == self._project
                )
            else:
                query = linear_joins(
                    self.session, tables, primary_filter=primary_filter
                )
            print("grid square query", query)
            if len(tables) == 1:
                return query.all()
            return [q[0] for q in query.all()]
        return []

    def get_foil_holes(
        self,
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
    ) -> List[FoilHole]:
        if self._project:
            primary_filter: Any = None
            end: Type[Base] = Tile
            if grid_square_name:
                end = FoilHole
                primary_filter = grid_square_name
            elif tile_id is not None:
                end = GridSquare
                primary_filter = tile_id
            elif atlas_id is not None:
                primary_filter = atlas_id
            tables = table_chain(FoilHole, end)
            if primary_filter is None:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == self._project
                )
            else:
                query = linear_joins(
                    self.session, tables, primary_filter=primary_filter
                )
            if len(tables) == 1:
                return query.all()
            return [q[0] for q in query.all()]
        return []

    def get_exposures(
        self,
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
        foil_hole_name: str = "",
    ) -> List[Exposure]:
        if self._project:
            primary_filter: Any = None
            end: Type[Base] = Tile
            if foil_hole_name:
                # print("foil hole name found to be", foil_hole_name)
                end = Exposure
                primary_filter = foil_hole_name
            elif grid_square_name:
                end = FoilHole
                primary_filter = grid_square_name
            elif tile_id is not None:
                end = GridSquare
                primary_filter = tile_id
            elif atlas_id is not None:
                primary_filter = atlas_id
            tables = table_chain(Exposure, end)
            if primary_filter is None:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == self._project
                )
            else:
                query = linear_joins(
                    self.session, tables, primary_filter=primary_filter
                )
            if len(tables) == 1:
                return query.all()
            return [q[0] for q in query.all()]
        return []

    def get_particles(
        self,
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
        foil_hole_name: str = "",
        exposure_name: str = "",
        source: str = "",
    ) -> List[Particle]:
        if self._project:
            if source:
                tables = [Particle, ParticleSet, ParticleSetLinker]
                query = linear_joins(self.session, tables)
                query = (
                    query.join(
                        Particle, Particle.particle_id == ParticleSetLinker.particle_id
                    )
                    .join(
                        ParticleSetLinker,
                        ParticleSetLinker.set_name == ParticleSet.identifier,
                    )
                    .filter(ParticleSet.project_name == self._project)
                )
            else:
                primary_filter: Any = None
                end: Type[Base] = Tile
                if exposure_name:
                    end = Particle
                    primary_filter = exposure_name
                elif foil_hole_name:
                    end = Exposure
                    primary_filter = foil_hole_name
                elif grid_square_name:
                    end = FoilHole
                    primary_filter = grid_square_name
                elif tile_id is not None:
                    end = GridSquare
                    primary_filter = tile_id
                elif atlas_id is not None:
                    primary_filter = atlas_id
                tables = table_chain(Particle, end)
                if primary_filter is None:
                    tables.append(Project)
                    query = linear_joins(self.session, tables, skip=[Project])
                    query = query.join(
                        Project, Project.atlas_id == Tile.atlas_id
                    ).filter(Project.project_name == self._project)
                else:
                    query = linear_joins(
                        self.session, tables, primary_filter=primary_filter
                    )
                print(query)
                if len(tables) == 1:
                    return query.all()
            return [q[0] for q in query.all()]
        return []

    def get_exposure_keys(self) -> List[str]:
        if not self._project:
            return []
        query = (
            self.session.query(
                Project, Tile, GridSquare, FoilHole, Exposure, ExposureInfo
            )
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(ExposureInfo).load_only("key"))  # type: ignore
            .join(Project, Project.atlas_id == Tile.atlas_id)
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(ExposureInfo, ExposureInfo.exposure_name == Exposure.exposure_name)
            .filter(Project.project_name == self._project)
            .distinct(ExposureInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_keys(self) -> List[str]:
        if not self._project:
            return []
        query = (
            self.session.query(
                Project, Tile, GridSquare, FoilHole, Exposure, Particle, ParticleInfo
            )
            .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(Particle).load_only("exposure_name", "particle_id"), Load(ParticleInfo).load_only("key"))  # type: ignore
            .join(Project, Project.atlas_id == Tile.atlas_id)
            .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(Project.project_name == self._project)
            .distinct(ParticleInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_set_keys(self) -> List[str]:
        if not self._project:
            return []
        query = (
            self.session.query(ParticleSet, ParticleSetInfo)
            .options(Load(ParticleSet).load_only("project_name", "identifier"), Load(ParticleSetInfo).load_only("key"))  # type: ignore
            .join(ParticleSet, ParticleSet.identifier == ParticleSetInfo.set_name)
            .filter(ParticleSet.project_name == self._project)
            .distinct(ParticleSetInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_set_group_names(self) -> List[str]:
        query = (
            self.session.query(ParticleSet, Project)
            .join(Project, Project.project_name == ParticleSet.project_name)
            .filter(Project.project_name == self._project)
            .distinct(ParticleSet.group_name)
        )
        return [q[0].group_name for q in query.all()]

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

    def get_particle_info_sources(self) -> List[str]:
        if self._project:
            query = (
                self.session.query(
                    Project,
                    Tile,
                    GridSquare,
                    FoilHole,
                    Exposure,
                    Particle,
                    ParticleInfo,
                )
                .options(Load(Tile).load_only("tile_id", "atlas_id"), Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"), Load(Particle).load_only("exposure_name", "particle_id"), Load(ParticleInfo).load_only("source"))  # type: ignore
                .join(GridSquare, GridSquare.tile_id == Tile.tile_id)
                .join(
                    FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name
                )
                .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
                .join(Particle, Particle.exposure_name == Exposure.exposure_name)
                .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
                .join(Project, Project.atlas_id == Tile.atlas_id)
                .filter(Project.project_name == self._project)
                .distinct(ParticleInfo.source)
            )
            return [q[-1].source for q in query.all()]
        return []

    def get_exposure_info(
        self,
        exposure_name: str,
        particle_keys: List[str],
        particle_set_keys: List[str],
    ) -> Dict[str, List[tuple]]:
        info = []
        if not any((particle_keys, particle_set_keys)):
            return info
        particle_query = (
            self.session.query(ParticleInfo, Particle)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(Particle.exposure_name == exposure_name)
            .order_by(Particle.particle_id)
        )
        particle_set_query = (
            self.session.query(ParticleSetInfo, ParticleSetLinker, Particle)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(Particle.exposure_name == exposure_name)
            .order_by(Particle.particle_id)
        )
        info.extend(particle_query.all())
        info.extend(particle_set_query.all())
        return info

    def get_foil_hole_info(
        self,
        foil_hole_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, List[tuple]]:
        info = []
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return info
        exposure_query = (
            self.session.query(ExposureInfo, Exposure)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .filter(ExposureInfo.key.in_(exposure_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
        )
        particle_query = (
            self.session.query(ParticleInfo, Particle, Exposure)
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
            .order_by(Particle.particle_id)
        )
        particle_set_query = (
            self.session.query(ParticleSetInfo, ParticleSetLinker, Particle, Exposure)
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(Exposure.foil_hole_name == foil_hole_name)
            .order_by(Particle.particle_id)
        )
        info.extend(exposure_query.all())
        info.extend(particle_query.all())
        info.extend(particle_set_query.all())
        return info

    def get_grid_square_info(
        self,
        grid_square_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, List[tuple]]:
        info = []
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return info
        exposure_query = (
            self.session.query(ExposureInfo, FoilHole, Exposure)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .filter(ExposureInfo.key.in_(exposure_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
            .order_by(Exposure.exposure_name)
        )
        particle_query = (
            self.session.query(ParticleInfo, FoilHole, Particle, Exposure)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
            .order_by(Particle.particle_id)
        )
        particle_set_query = (
            self.session.query(ParticleSetInfo, ParticleSetLinker, Particle, Exposure)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
            .order_by(Particle.particle_id)
        )
        info.extend(exposure_query.all())
        info.extend(particle_query.all())
        info.extend(particle_set_query.all())
        return info

    def put(self, entries: Sequence[Base]):
        for entry in entries:
            self.session.add(entry)
        self.session.commit()


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

    def get_all_exposures_for_grid_square(
        self, grid_square_name: str
    ) -> List[Exposure]:
        query = (
            self.session.query(FoilHole, Exposure)
            .options(Load(FoilHole).load_only("grid_square_name", "foil_hole_name"), Load(Exposure).load_only("foil_hole_name", "exposure_name"))  # type: ignore
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .filter(FoilHole.grid_square_name == grid_square_name)
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
            self.session.query(ParticleSet, Project)
            .join(Project, Project.project_name == ParticleSet.project_name)
            .filter(Project.atlas_id == self._atlas_id)
            .distinct(ParticleSet.group_name)
        )
        return [q[0].group_name for q in query.all()]

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
            self.session.query(Project, ParticleSet, ParticleSetInfo)
            .options(Load(ParticleSet).load_only("atlas_id", "identifier"), Load(ParticleSetInfo).load_only("key"))  # type: ignore
            .join(ParticleSet, ParticleSet.identifier == ParticleSetInfo.set_name)
            .join(Project, Project.project_name == ParticleSet.project_name)
            .filter(Project.atlas_id == self._atlas_id)
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

    def get_particles(
        self,
        exposure_name: str,
        source: Optional[str] = None,
        group_name: Optional[str] = None,
    ) -> List[Particle]:
        if not source and not group_name:
            query = self.session.query(Particle).filter(
                Particle.exposure_name == exposure_name
            )
            return query.all()
        elif not source:
            query = (
                self.session.query(Particle, ParticleSet, ParticleSetLinker)
                .join(Particle, Particle.particle_id == ParticleSetLinker.particle_id)
                .join(ParticleSet, ParticleSet.identifier == ParticleSetLinker.set_name)
                .filter(Particle.exposure_name == exposure_name)
                .filter(ParticleSet.group_name == group_name)
            )
            return [q[0] for q in query.all()]
        query = (
            self.session.query(Particle, ParticleInfo)
            .join(Particle, Particle.particle_id == ParticleInfo.particle_id)
            .filter(ParticleInfo.source == source)
            .filter(Particle.exposure_name == exposure_name)
        )
        return [q[0] for q in query.all()]

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
    ) -> Dict[str, List[Optional[float]]]:
        stats: Dict[str, List[Optional[float]]] = {}
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
            .order_by(Particle.particle_id)
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
            .order_by(Particle.particle_id)
        )
        exposure_results = exposure_query.all()
        particle_results = particle_query.all()
        particle_set_results = particle_set_query.all()
        for k in exposure_keys:
            stats[k] = []
            for exp in exposures:
                this_res = [
                    er[-1].value
                    for er in exposure_results
                    if er[-1].key == k and er[0].exposure_name == exp
                ]
                if this_res:
                    stats[k].append(this_res[0])
                else:
                    stats[k].append(0)
        if particle_keys:
            stats.update(
                _parse_particle_data(
                    particle_keys,
                    particle_results,
                    exposures,
                    avg_particles=avg_particles,
                )
            )
        if particle_set_keys:
            stats.update(
                _parse_particle_data(
                    particle_set_keys,
                    particle_set_results,
                    exposures,
                    avg_particles=avg_particles,
                )
            )
        return stats

    def get_grid_square_stats_all(
        self,
        grid_square_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, Dict[str, List[Optional[float]]]]:
        stats: Dict[str, Dict[str, List[Optional[float]]]] = {}
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

    def get_grid_square_stats_flat(
        self,
        grid_square_name: str,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, List[Optional[float]]]:
        stats: Dict[str, List[Optional[float]]] = {
            k: [] for k in exposure_keys + particle_keys + particle_set_keys
        }
        exposure_query = (
            self.session.query(FoilHole, Exposure, ExposureInfo)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .filter(ExposureInfo.key.in_(exposure_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
        )
        particle_query = (
            self.session.query(FoilHole, Exposure, Particle, ParticleInfo)
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
            .order_by(Particle.particle_id)
        )
        particle_set_query = (
            self.session.query(
                FoilHole, Exposure, Particle, ParticleSetLinker, ParticleSetInfo
            )
            .join(Exposure, Exposure.exposure_name == Particle.exposure_name)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(FoilHole.grid_square_name == grid_square_name)
            .order_by(Particle.particle_id)
        )
        exposures = self.get_all_exposures_for_grid_square(grid_square_name)
        exposure_results = exposure_query.all()
        particle_results = particle_query.all()
        particle_set_results = particle_set_query.all()
        for k in exposure_keys:
            for exp in exposures:
                this_res = [
                    er[-1].value
                    for er in exposure_results
                    if er[-1].key == k and er[1].exposure_name == exp.exposure_name
                ]
                if this_res:
                    stats[k].append(this_res[0])
                else:
                    stats[k].append(0)
        if particle_keys:
            stats.update(
                _parse_particle_data(
                    particle_keys,
                    particle_results,
                    [e.exposure_name for e in exposures],
                    exposure_index=1,
                    avg_particles=avg_particles,
                )
            )
        if particle_set_keys:
            stats.update(
                _parse_particle_data(
                    particle_set_keys,
                    particle_set_results,
                    [e.exposure_name for e in exposures],
                    exposure_index=1,
                    avg_particles=avg_particles,
                )
            )
        return stats

    def get_atlas_stats_flat(
        self,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
        avg_particles: bool = False,
    ) -> Dict[str, Dict[str, List[Optional[float]]]]:
        stats: Dict[str, Dict[str, List[Optional[float]]]] = {
            k: {} for k in exposure_keys + particle_keys + particle_set_keys
        }
        grid_squares = self.get_grid_squares()
        for gs in grid_squares:
            gs_stats = self.get_grid_square_stats_flat(
                gs.grid_square_name,
                exposure_keys,
                particle_keys,
                particle_set_keys,
                avg_particles=avg_particles,
            )
            for k, v in gs_stats.items():
                stats[k][gs.grid_square_name] = v
        return stats


def _parse_particle_data(
    keys: List[str],
    data: list,
    exposures: List[str],
    info_index: int = -1,
    exposure_index: int = 0,
    avg_particles: bool = False,
) -> dict:
    stats: dict = {}
    for k in keys:
        stats[k] = []
        for exp in exposures:
            if avg_particles:
                stats[k].append(
                    np.mean(
                        [
                            er[info_index].value
                            for er in data
                            if er[info_index].key == k
                            and er[exposure_index].exposure_name == exp
                        ]
                    )
                )
            else:
                stats[k].extend(
                    er[info_index].value
                    for er in data
                    if er[info_index].key == k
                    and er[exposure_index].exposure_name == exp
                )
    return stats
