from typing import Any, List, Optional, Sequence, Set, Tuple, Type, Union

from sqlalchemy import create_engine
from sqlalchemy.orm import Load, load_only, sessionmaker

from smartem.data_model import (
    Atlas,
    Base,
    Exposure,
    ExposureInfo,
    FoilHole,
    GridSquare,
    Particle,
    ParticleInfo,
    ParticleSet,
    ParticleSetInfo,
    ParticleSetLinker,
    Project,
    Tile,
    url,
)
from smartem.data_model.construct import linear_joins, table_chain


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

    def update_project(
        self,
        project_name: str,
        acquisition_directory: str = "",
        processing_directory: str = "",
    ):
        updated_values = {}
        if acquisition_directory:
            updated_values["acquisition_directory"] = acquisition_directory
        if processing_directory:
            updated_values["processing_directory"] = processing_directory
        if not updated_values:
            return
        self.session.query(Project).filter(Project.project_name == project_name).update(
            updated_values
        )
        self.session.commit()

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

    def update_atlas(self, atlas_id: int, thumbnail: str = ""):
        updated_values = {}
        if thumbnail:
            updated_values["thumbnail"] = thumbnail
        if not updated_values:
            return
        self.session.query(Atlas).filter(Atlas.atlas_id == atlas_id).update(
            updated_values
        )
        self.session.commit()

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

    def get_tile_id(self, stage_position: Tuple[float, float]) -> Optional[int]:
        tile = self.get_tile(stage_position)
        if tile:
            return tile.tile_id
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
                if len(tables) == 1:
                    return query.all()
            return [q[0] for q in query.all()]
        return []

    def get_particle_sets(
        self, group_name: str, set_ids: Union[Set[str], List[str]], source_name: str
    ) -> List[ParticleSet]:
        if not self._project:
            return []
        query = (
            self.session.query(ParticleSet)
            .filter(ParticleSet.project_name == self._project)
            .filter(ParticleSet.group_name == group_name)
            .filter(ParticleSet.identifier.in_([f"{source_name}:{s}" for s in set_ids]))
        )
        q = query.all()
        return q

    def get_particle_linkers(
        self, set_ids: Union[Set[str], List[str]], source_name: str
    ) -> List[ParticleSetLinker]:
        if not self._project:
            return []
        query = (
            self.session.query(ParticleSetLinker, ParticleSet)
            .join(ParticleSet, ParticleSet.identifier == ParticleSetLinker.set_name)
            .filter(ParticleSet.project_name == self._project)
            .filter(
                ParticleSetLinker.set_name.in_([f"{source_name}:{s}" for s in set_ids])
            )
        )
        return [q[0] for q in query.all()]

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
    ) -> List[tuple]:
        info: List[tuple] = []
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
    ) -> List[tuple]:
        info: List[tuple] = []
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
    ) -> List[tuple]:
        info: List[tuple] = []
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
            self.session.query(
                ParticleSetInfo, ParticleSetLinker, FoilHole, Particle, Exposure
            )
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

    def get_atlas_info(
        self,
        atlas_id: int,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
    ) -> List[tuple]:
        info: List[tuple] = []
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return info
        exposure_query = (
            self.session.query(ExposureInfo, FoilHole, GridSquare, Tile, Exposure)
            .join(Exposure, Exposure.exposure_name == ExposureInfo.exposure_name)
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .join(GridSquare, GridSquare.grid_square_name == FoilHole.grid_square_name)
            .join(Tile, Tile.tile_id == GridSquare.tile_id)
            .filter(ExposureInfo.key.in_(exposure_keys))
            .filter(Tile.atlas_id == atlas_id)
            .order_by(Exposure.exposure_name)
        )
        particle_query = (
            self.session.query(
                ParticleInfo, FoilHole, Particle, GridSquare, Tile, Exposure
            )
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(GridSquare, GridSquare.grid_square_name == FoilHole.grid_square_name)
            .join(Tile, Tile.tile_id == GridSquare.tile_id)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .filter(ParticleInfo.key.in_(particle_keys))
            .filter(Tile.atlas_id == atlas_id)
            .order_by(Particle.particle_id)
        )
        particle_set_query = (
            self.session.query(
                ParticleSetInfo,
                ParticleSetLinker,
                FoilHole,
                GridSquare,
                Particle,
                Tile,
                Exposure,
            )
            .join(FoilHole, FoilHole.foil_hole_name == Exposure.foil_hole_name)
            .join(GridSquare, GridSquare.grid_square_name == FoilHole.grid_square_name)
            .join(Tile, Tile.tile_id == GridSquare.tile_id)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(
                ParticleSetLinker, ParticleSetLinker.particle_id == Particle.particle_id
            )
            .join(
                ParticleSetInfo, ParticleSetInfo.set_name == ParticleSetLinker.set_name
            )
            .filter(ParticleSetInfo.key.in_(particle_set_keys))
            .filter(Tile.atlas_id == atlas_id)
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
