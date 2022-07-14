from typing import Any, List, Optional, Sequence, Set, Tuple, Type, Union

from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.row import LegacyRow
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
        self.engine = create_engine(_url)
        self.session = sessionmaker(bind=self.engine)()

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

    def get_atlases(self, project: str = "") -> Union[Atlas, List[Atlas]]:
        if project:
            query = (
                self.session.query(Project, Atlas)
                .join(Project, Project.atlas_id == Atlas.atlas_id)
                .filter(Project.project_name == project)
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
        self,
        stage_position: Tuple[float, float],
        atlas_id: Optional[int] = None,
        project: str = "",
    ) -> Optional[Tile]:
        if atlas_id is None and project:
            atlas = self.get_atlases(project=project)
            if not atlas or isinstance(atlas, list):
                return None
            atlas_id = atlas.atlas_id
        else:
            raise ValueError("One of atlas_id or project must be specified")
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

    def get_tile_id(
        self, stage_position: Tuple[float, float], project: str
    ) -> Optional[int]:
        tile = self.get_tile(stage_position, project=project)
        if tile:
            return tile.tile_id
        return None

    def get_grid_squares(
        self,
        project: str,
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
    ) -> List[GridSquare]:
        if any((project, atlas_id, tile_id)):
            primary_filter: Any = None
            end: Type[Base] = Tile
            if tile_id is not None:
                end = GridSquare
                primary_filter = tile_id
            elif atlas_id is not None:
                primary_filter = atlas_id
            tables = table_chain(GridSquare, end)
            if project:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == project
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
        project: str = "",
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
    ) -> List[FoilHole]:
        if any((project, atlas_id, tile_id, grid_square_name)):
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
            if project:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == project
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
        project: str = "",
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
        foil_hole_name: str = "",
    ) -> List[Exposure]:
        if any((project, atlas_id, tile_id, grid_square_name, foil_hole_name)):
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
            if project:
                tables.append(Project)
                query = linear_joins(self.session, tables, skip=[Project])
                query = query.join(Project, Project.atlas_id == Tile.atlas_id).filter(
                    Project.project_name == project
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
        project: str = "",
        atlas_id: Optional[int] = None,
        tile_id: Optional[int] = None,
        grid_square_name: str = "",
        foil_hole_name: str = "",
        exposure_name: str = "",
        source: str = "",
    ) -> List[Particle]:
        res = []
        particle_batch_size = 500000
        if any(
            (
                project,
                atlas_id,
                tile_id,
                grid_square_name,
                foil_hole_name,
                exposure_name,
                source,
            )
        ):
            if source:
                if not project:
                    raise ValueError(
                        "If source is provided then project must also be provided"
                    )
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
                    .filter(ParticleSet.project_name == project)
                )
                particle_count = query.count()
                num_full_batches = particle_count // particle_batch_size
                for b in range(num_full_batches + 1):
                    if len(tables) == 1:
                        res.extend(
                            query.limit(particle_batch_size)
                            .offset(b * particle_batch_size)
                            .all()
                        )
                    else:
                        res.extend(
                            q[0]
                            for q in query.order_by(Particle.particle_id)
                            .limit(particle_batch_size)
                            .offset(b * particle_batch_size)
                            .all()
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
                if project:
                    tables.append(Project)
                    query = linear_joins(self.session, tables, skip=[Project])
                    query = query.join(
                        Project, Project.atlas_id == Tile.atlas_id
                    ).filter(Project.project_name == project)
                else:
                    query = linear_joins(
                        self.session, tables, primary_filter=primary_filter
                    )
                particle_count = query.count()
                num_full_batches = particle_count // particle_batch_size
                for b in range(num_full_batches + 1):
                    if len(tables) == 1:
                        res.extend(
                            query.order_by(Particle.particle_id)
                            .limit(particle_batch_size)
                            .offset(b * particle_batch_size)
                            .all()
                        )
                    else:
                        res.extend(
                            q[0]
                            for q in query.order_by(Particle.particle_id)
                            .limit(particle_batch_size)
                            .offset(b * particle_batch_size)
                            .all()
                        )
            return res
        return []

    def get_particle_sets(
        self,
        project: str,
        group_name: str = "",
        set_ids: Optional[Union[Set[str], List[str]]] = None,
        source_name: str = "",
    ) -> List[ParticleSet]:
        if not any([group_name, set_ids, source_name]):
            query = self.session.query(ParticleSet).filter(
                ParticleSet.project_name == project
            )
        elif set_ids:
            query = (
                self.session.query(ParticleSet)
                .filter(ParticleSet.project_name == project)
                .filter(ParticleSet.group_name == group_name)
                .filter(
                    ParticleSet.identifier.in_([f"{source_name}:{s}" for s in set_ids])
                )
            )
        else:
            raise ValueError(
                "If group_name or source_name are specified then set_ids must also be specified"
            )
        q = query.all()
        return q

    def get_particle_linkers(
        self, project: str, set_ids: Union[Set[str], List[str]], source_name: str
    ) -> List[ParticleSetLinker]:
        res: List[ParticleSetLinker] = []
        particle_batch_size = 500000
        query = (
            self.session.query(ParticleSetLinker, ParticleSet)
            .join(ParticleSet, ParticleSet.identifier == ParticleSetLinker.set_name)
            .filter(ParticleSet.project_name == project)
            .filter(
                ParticleSetLinker.set_name.in_([f"{source_name}:{s}" for s in set_ids])
            )
        )
        particle_count = query.count()
        num_full_batches = particle_count // particle_batch_size
        for b in range(num_full_batches + 1):
            res.extend(
                q[0]
                for q in query.order_by(ParticleSetLinker.particle_id)
                .limit(particle_batch_size)
                .offset(b * particle_batch_size)
                .all()
            )
        return res

    def get_exposure_keys(self, project: str) -> List[str]:
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
            .filter(Project.project_name == project)
            .distinct(ExposureInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_keys(self, project: str) -> List[str]:
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
            .filter(Project.project_name == project)
            .distinct(ParticleInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_set_keys(self, project: str) -> List[str]:
        query = (
            self.session.query(ParticleSet, ParticleSetInfo)
            .options(Load(ParticleSet).load_only("project_name", "identifier"), Load(ParticleSetInfo).load_only("key"))  # type: ignore
            .join(ParticleSet, ParticleSet.identifier == ParticleSetInfo.set_name)
            .filter(ParticleSet.project_name == project)
            .distinct(ParticleSetInfo.key)
        )
        return [q[-1].key for q in query.all()]

    def get_particle_set_group_names(self, project: str) -> List[str]:
        query = (
            self.session.query(ParticleSet, Project)
            .join(Project, Project.project_name == ParticleSet.project_name)
            .filter(Project.project_name == project)
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

    def get_particle_info_sources(self, project: str) -> List[str]:
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
            .join(FoilHole, FoilHole.grid_square_name == GridSquare.grid_square_name)
            .join(Exposure, Exposure.foil_hole_name == FoilHole.foil_hole_name)
            .join(Particle, Particle.exposure_name == Exposure.exposure_name)
            .join(ParticleInfo, ParticleInfo.particle_id == Particle.particle_id)
            .join(Project, Project.atlas_id == Tile.atlas_id)
            .filter(Project.project_name == project)
            .distinct(ParticleInfo.source)
        )
        return [q[-1].source for q in query.all()]

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
    ) -> List[LegacyRow]:
        info: List[tuple] = []
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return info
        exposure_query = (
            select(
                (
                    Exposure.exposure_name,
                    FoilHole.foil_hole_name,
                    ExposureInfo.key,
                    ExposureInfo.value,
                ),
            )
            .select_from(
                ExposureInfo.__table__.join(
                    Exposure.__table__,
                    Exposure.exposure_name == ExposureInfo.exposure_name,
                ).join(
                    FoilHole.__table__,
                    Exposure.foil_hole_name == FoilHole.foil_hole_name,
                )
            )
            .where(
                ExposureInfo.key.in_(exposure_keys),
            )
            .where(FoilHole.grid_square_name == grid_square_name)
            .order_by(Exposure.exposure_name)
        )
        with self.engine.connect() as connection:
            info.extend(connection.execute(exposure_query).fetchall())

        if particle_keys:
            particle_query = (
                select(
                    (
                        Particle.particle_id,
                        Particle.x,
                        Particle.y,
                        Exposure.exposure_name,
                        FoilHole.foil_hole_name,
                        ParticleInfo.key,
                        ParticleInfo.value,
                    ),
                )
                .select_from(
                    ParticleInfo.__table__.join(
                        Particle.__table__,
                        Particle.particle_id == ParticleInfo.particle_id,
                    )
                    .join(
                        Exposure.__table__,
                        Particle.exposure_name == Exposure.exposure_name,
                    )
                    .join(
                        FoilHole.__table__,
                        Exposure.foil_hole_name == FoilHole.foil_hole_name,
                    )
                )
                .where(
                    ParticleInfo.key.in_(particle_keys),
                )
                .where(FoilHole.grid_square_name == grid_square_name)
                .order_by(Particle.particle_id)
            )
            with self.engine.connect() as connection:
                info.extend(connection.execute(particle_query).fetchall())

        if particle_set_keys:
            particle_set_query = (
                select(
                    (
                        Particle.particle_id,
                        Particle.x,
                        Particle.y,
                        Exposure.exposure_name,
                        FoilHole.foil_hole_name,
                        ParticleSetInfo.key,
                        ParticleSetInfo.value,
                    ),
                )
                .select_from(
                    ParticleSetInfo.__table__.join(
                        ParticleSetLinker.__table__,
                        ParticleSetLinker.set_name == ParticleSetInfo.set_name,
                    )
                    .join(
                        Particle.__table__,
                        Particle.particle_id == ParticleSetLinker.particle_id,
                    )
                    .join(
                        Exposure.__table__,
                        Particle.exposure_name == Exposure.exposure_name,
                    )
                    .join(
                        FoilHole.__table__,
                        Exposure.foil_hole_name == FoilHole.foil_hole_name,
                    )
                )
                .where(ParticleSetInfo.key.in_(particle_set_keys))
                .where(FoilHole.grid_square_name == grid_square_name)
                .order_by(Particle.particle_id)
            )
            with self.engine.connect() as connection:
                info.extend(connection.execute(particle_set_query).fetchall())
        return info

    def get_atlas_info(
        self,
        atlas_id: int,
        exposure_keys: List[str],
        particle_keys: List[str],
        particle_set_keys: List[str],
    ) -> List[LegacyRow]:
        info: List[tuple] = []
        if not any((exposure_keys, particle_keys, particle_set_keys)):
            return info
        exposure_query = (
            select(
                (
                    Exposure.exposure_name,
                    FoilHole.foil_hole_name,
                    GridSquare.grid_square_name,
                    ExposureInfo.key,
                    ExposureInfo.value,
                ),
            )
            .select_from(
                ExposureInfo.__table__.join(
                    Exposure.__table__,
                    Exposure.exposure_name == ExposureInfo.exposure_name,
                )
                .join(
                    FoilHole.__table__,
                    Exposure.foil_hole_name == FoilHole.foil_hole_name,
                )
                .join(
                    GridSquare.__table__,
                    FoilHole.grid_square_name == GridSquare.grid_square_name,
                )
                .join(Tile.__table__, GridSquare.tile_id == Tile.tile_id)
            )
            .where(ExposureInfo.key.in_(exposure_keys))
            .where(Tile.atlas_id == atlas_id)
            .order_by(Exposure.exposure_name)
        )
        with self.engine.connect() as connection:
            info.extend(connection.execute(exposure_query).fetchall())

        if particle_keys:
            particle_query = (
                select(
                    (
                        Particle.particle_id,
                        Particle.x,
                        Particle.y,
                        Exposure.exposure_name,
                        FoilHole.foil_hole_name,
                        GridSquare.grid_square_name,
                        ParticleInfo.key,
                        ParticleInfo.value,
                    ),
                )
                .select_from(
                    ParticleInfo.__table__.join(
                        Particle.__table__,
                        Particle.particle_id == ParticleInfo.particle_id,
                    )
                    .join(
                        Exposure.__table__,
                        Particle.exposure_name == Exposure.exposure_name,
                    )
                    .join(
                        FoilHole.__table__,
                        Exposure.foil_hole_name == FoilHole.foil_hole_name,
                    )
                    .join(
                        GridSquare.__table__,
                        FoilHole.grid_square_name == GridSquare.grid_square_name,
                    )
                    .join(Tile.__table__, GridSquare.tile_id == Tile.tile_id)
                )
                .where(ParticleInfo.key.in_(particle_keys))
                .where(Tile.atlas_id == atlas_id)
                .order_by(Particle.particle_id)
            )
            with self.engine.connect() as connection:
                info.extend(connection.execute(particle_query).fetchall())

        if particle_set_keys:
            particle_set_query = (
                select(
                    (
                        Particle.particle_id,
                        Particle.x,
                        Particle.y,
                        Exposure.exposure_name,
                        FoilHole.foil_hole_name,
                        GridSquare.grid_square_name,
                        ParticleSetInfo.key,
                        ParticleSetInfo.value,
                    ),
                )
                .select_from(
                    ParticleSetInfo.__table__.join(
                        ParticleSetLinker.__table__,
                        ParticleSetLinker.set_name == ParticleSetInfo.set_name,
                    )
                    .join(
                        Particle.__table__,
                        Particle.particle_id == ParticleSetLinker.particle_id,
                    )
                    .join(
                        Exposure.__table__,
                        Particle.exposure_name == Exposure.exposure_name,
                    )
                    .join(
                        FoilHole.__table__,
                        Exposure.foil_hole_name == FoilHole.foil_hole_name,
                    )
                    .join(
                        GridSquare.__table__,
                        FoilHole.grid_square_name == GridSquare.grid_square_name,
                    )
                    .join(Tile.__table__, GridSquare.tile_id == Tile.tile_id)
                )
                .where(
                    ParticleSetInfo.key.in_(particle_set_keys),
                )
                .where(Tile.atlas_id == atlas_id)
                .order_by(Particle.particle_id)
            )
            with self.engine.connect() as connection:
                result = connection.execute(particle_set_query).fetchall()
                info.extend(result)
        return info

    def put(self, entries: Sequence[Base], allow_duplicates: bool = True) -> list:
        if not entries:
            return []
        table = entries[0].__table__  # type: ignore
        rows = [
            {k: v for k, v in e.__dict__.items() if k != "_sa_instance_state"}
            for e in entries
        ]
        with self.engine.connect() as connection:
            with connection.begin():
                insert_stmt = insert(table).values(rows)
                if allow_duplicates:
                    insert_stmt = insert_stmt.returning(
                        table.primary_key.columns.values()[0]
                    ).on_conflict_do_update(
                        constraint=table.primary_key, set_=table.columns
                    )
                result = connection.execute(insert_stmt)
        return result.fetchall()

    def delete_project(self, project: str):
        stmts = []
        particle_sets = self.get_particle_sets(project=project)
        psids = [p.identifier for p in particle_sets]
        psi_table = ParticleSetInfo.__table__
        psi_delete_stmt = delete(psi_table).where(psi_table.c.set_name.in_(psids))
        stmts.append(psi_delete_stmt)
        linker_table = ParticleSetLinker.__table__
        linker_delete_stmt = delete(linker_table).where(
            linker_table.c.set_name.in_(psids)
        )
        stmts.append(linker_delete_stmt)
        ps_table = ParticleSet.__table__
        ps_delete_stmt = delete(ps_table).where(ps_table.c.project_name == project)
        stmts.append(ps_delete_stmt)
        particles = self.get_particles(project=project)
        pids = [p.particle_id for p in particles]
        pi_table = ParticleInfo.__table__
        pi_delete_stmt = delete(pi_table).where(pi_table.c.particle_id.in_(pids))
        stmts.append(pi_delete_stmt)
        par_table = Particle.__table__
        par_delete_stmt = delete(par_table).where(par_table.c.particle_id.in_(pids))
        stmts.append(par_delete_stmt)
        exposures = self.get_exposures(project=project)
        enames = [e.exposure_name for e in exposures]
        ei_table = ExposureInfo.__table__
        ei_delete_stmt = delete(ei_table).where(ei_table.c.exposure_name.in_(enames))
        stmts.append(ei_delete_stmt)
        exp_table = Exposure.__table__
        exp_delete_stmt = delete(exp_table).where(exp_table.c.exposure_name.in_(enames))
        stmts.append(exp_delete_stmt)
        foil_holes = self.get_foil_holes(project=project)
        fh_names = [fh.foil_hole_name for fh in foil_holes]
        fh_table = FoilHole.__table__
        fh_delete_stmt = delete(fh_table).where(fh_table.c.foil_hole_name.in_(fh_names))
        stmts.append(fh_delete_stmt)
        grid_squares = self.get_grid_squares(project=project)
        gs_names = [gs.grid_square_name for gs in grid_squares]
        gs_table = GridSquare.__table__
        gs_delete_stmt = delete(gs_table).where(
            gs_table.c.grid_square_name.in_(gs_names)
        )
        stmts.append(gs_delete_stmt)
        atlases = self.get_atlases(project=project)
        if isinstance(atlases, Atlas):
            atlas_ids = [atlases.atlas_id]
        else:
            atlas_ids = [a.atlas_id for a in atlases]
        tile_table = Tile.__table__
        tile_delete_stmt = delete(tile_table).where(
            tile_table.c.atlas_id.in_(atlas_ids)
        )
        stmts.append(tile_delete_stmt)
        proj_table = Project.__table__
        proj_delete_stmt = delete(proj_table).where(
            proj_table.c.project_name == project
        )
        stmts.append(proj_delete_stmt)
        atlas_table = Atlas.__table__
        atlas_delete_stmt = delete(atlas_table).where(
            atlas_table.c.atlas_id.in_(atlas_ids)
        )
        stmts.append(atlas_delete_stmt)
        with self.engine.connect() as connection:
            with connection.begin():
                for st in stmts:
                    connection.execute(st)
