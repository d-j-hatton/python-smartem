import pytest
from unittest import mock, TestCase

from smartem.data_model import Project
from smartem.data_model import extract


class TestDataAPI(TestCase):
    @mock.patch("smartem.data_model.extract.url")
    @mock.patch("smartem.data_model.extract.create_engine")
    @mock.patch("smartem.data_model.extract.sessionmaker")
    def setUp(self, mock_session, mock_engine, mock_url):
        mock_url.return_value = "test_url1"
        mock_engine.return_value = mock.MagicMock()
        mock_session.return_value = mock.MagicMock()
        self.test_api = extract.DataAPI(project="test")

    def test_set_project(self):
        self.test_api.set_project(project="test")

        self.test_api.session.query().options().all.assert_called_once()
        assert self.test_api._project == "test"

    def test_get_project(self):
        self.test_api.get_project(project_name="test")

        self.test_api.session.query().options().filter.assert_called_once()
        self.test_api.session.query().options().filter().all.assert_called_once()

    def test_update_project(self):
        self.test_api.update_project(
            project_name="test",
            acquisition_directory="new_dir_1",
            processing_directory="new_dir_2"
        )

        self.test_api.session.query().filter().update.assert_called_once()
        self.test_api.session.commit.assert_called_once()

    def test_get_projects(self):
        return_value = self.test_api.get_projects()

        assert type(return_value) == list
        self.test_api.session.query().options().all.assert_called_once()

    def test_get_atlas_from_project(self):
        test_project = Project()
        try:
            self.test_api.get_atlas_from_project(project=test_project)
        except IndexError:
            pass

        self.test_api.session.query().join().filter.assert_called_once()
        self.test_api.session.query().join().filter().all.assert_called_once()

    def test_get_atlases(self):
        return_value = self.test_api.get_atlases(project="test")

        assert type(return_value) == list
        self.test_api.session.query().join().filter.assert_called_once()
        self.test_api.session.query().join().filter().all.assert_called_once()

    def test_update_atlas(self):
        self.test_api.update_atlas(atlas_id=0, thumbnail="test")

        self.test_api.session.query().filter().update.assert_called_once()
        self.test_api.session.commit.assert_called_once()

    @mock.patch("smartem.data_model.extract.DataAPI.get_atlases")
    def test_get_tile(self, mock_get_atlases):
        class MockAtlas:
            atlas_id = 0

        mock_get_atlases.return_value = MockAtlas()

        return_value = self.test_api.get_tile(
            stage_position=[0, 0],
            project="test"
        )

        assert return_value is None
        self.test_api.session.query().filter.assert_called_once()
        self.test_api.session.query().filter().all.assert_called_once()

    def test_get_tile_id(self):
        return_value = self.test_api.get_tile_id(
            stage_position=[0, 0],
            project="test"
        )

        assert return_value is None

    @mock.patch("smartem.data_model.extract.linear_joins")
    def test_get_grid_squares(self, mock_join):
        mock_join.return_value = mock.MagicMock()
        return_value = self.test_api.get_grid_squares(
            project="test",
            atlas_id=1,
            tile_id=1
        )

        assert return_value == []
        mock_join.assert_called_once()
        mock_join().join().filter.assert_called_once()
        mock_join().join().filter().all.assert_called_once()

    @mock.patch("smartem.data_model.extract.linear_joins")
    def test_get_foil_holes(self, mock_join):
        mock_join.return_value = mock.MagicMock()
        return_value = self.test_api.get_foil_holes(
            project="test",
            atlas_id=1,
            tile_id=1,
            grid_square_name="test_square"
        )

        assert return_value == []
        mock_join.assert_called_once()
        mock_join().join().filter.assert_called_once()
        mock_join().join().filter().all.assert_called_once()

    @mock.patch("smartem.data_model.extract.linear_joins")
    def test_get_exposures(self, mock_join):
        mock_join.return_value = mock.MagicMock()
        return_value = self.test_api.get_exposures(
            project="test",
            atlas_id=1,
            tile_id=1,
            grid_square_name="test_square",
            foil_hole_name="test_hole"
        )

        assert return_value == []
        mock_join.assert_called_once()
        mock_join().join().filter.assert_called_once()
        mock_join().join().filter().all.assert_called_once()

    @mock.patch("smartem.data_model.extract.linear_joins")
    def test_get_particles_with_source(self, mock_join):
        mock_join.return_value = mock.MagicMock()
        return_value = self.test_api.get_particles(
            project="test",
            atlas_id=1,
            tile_id=1,
            grid_square_name="test_square",
            foil_hole_name="test_hole",
            exposure_name="test_exposure",
            source="test_source"
        )

        assert type(return_value) == list
        mock_join.assert_called_once()
        mock_join().join().join().filter.assert_called_once()
        mock_join().join().join().filter().count.assert_called_once()
        mock_join().join().join().filter().order_by().limit().offset().all.assert_called_once()

    @mock.patch("smartem.data_model.extract.linear_joins")
    def test_get_particles_without_source(self, mock_join):
        mock_join.return_value = mock.MagicMock()
        return_value = self.test_api.get_particles(
            project="test",
            atlas_id=1,
            tile_id=1,
            grid_square_name="test_square",
            foil_hole_name="test_hole",
            exposure_name="test_exposure",
        )

        assert type(return_value) == list
        mock_join.assert_called_once()
        mock_join().join().filter.assert_called_once()
        mock_join().join().filter().count.assert_called_once()
        mock_join().join().filter().order_by().limit().offset().all.assert_called_once()

    def test_get_particle_sets(self):
        return_value = self.test_api.get_particle_sets(
            project="test",
            group_name="test_group",
            set_ids=[1, 2],
            source_name="test_source"
        )

        assert return_value
        self.test_api.session.query().filter().filter().filter.assert_called_once()
        self.test_api.session.query().filter().filter().filter().all.assert_called_once()

    def test_get_particle_linkers(self):
        return_value = self.test_api.get_particle_linkers(
            project="test",
            set_ids=[1, 2],
            source_name="test_source"
        )

        assert type(return_value) == list
        self.test_api.session.query().join().filter().filter.assert_called_once()
        self.test_api.session.query().join().filter().filter().count.assert_called_once()
        self.test_api.session.query().join().filter().filter().order_by().limit().offset().all.assert_called_once()

    def test_get_exposure_keys(self):
        return_value = self.test_api.get_exposure_keys(project="test")

        assert type(return_value) == list
        self.test_api.session.query().options().join().join().join().join().join().filter().distinct.assert_called_once()
        self.test_api.session.query().options().join().join().join().join().join().filter().distinct().all.assert_called_once()

    def test_get_particle_keys(self):
        return_value = self.test_api.get_particle_keys(project="test")

        assert type(return_value) == list
        self.test_api.session.query().options().join().join().join().join().join().join().filter().distinct.assert_called_once()
        self.test_api.session.query().options().join().join().join().join().join().join().filter().distinct().all.assert_called_once()

    def test_get_particle_set_keys(self):
        return_value = self.test_api.get_particle_set_keys(project="test")

        assert type(return_value) == list
        self.test_api.session.query().options().join().filter().distinct.assert_called_once()
        self.test_api.session.query().options().join().filter().distinct().all.assert_called_once()

    def test_get_particle_set_group_names(self):
        return_value = self.test_api.get_particle_set_group_names(project="test")

        assert type(return_value) == list
        self.test_api.session.query().join().filter().distinct.assert_called_once()
        self.test_api.session.query().join().filter().distinct().all.assert_called_once()

    def test_get_particle_id(self):
        self.test_api.get_particle_id(
            exposure_name="test_exposure",
            x=0.5,
            y=1.5
        )

        self.test_api.session.query().filter.assert_called_once()
        self.test_api.session.query().filter().all.assert_called_once()

    def test_get_particle_info_sources(self):
        return_value = self.test_api.get_particle_info_sources(project="test")

        assert type(return_value) == list
        self.test_api.session.query().options().join().join().join().join().join().join().filter().distinct.assert_called_once()
        self.test_api.session.query().options().join().join().join().join().join().join().filter().distinct().all.assert_called_once()

    def test_get_exposure_info(self):
        return_value = self.test_api.get_exposure_info(
            exposure_name="test_exposure",
            particle_keys=["test_key"],
            particle_set_keys=["test_set_key"]
        )

        assert type(return_value) == list
        self.test_api.session.query().join().filter().filter().order_by.assert_called_once()
        self.test_api.session.query().join().join().filter().filter().order_by.assert_called_once()
        self.test_api.session.query().join().filter().filter().order_by().all.assert_called_once()
        self.test_api.session.query().join().join().filter().filter().order_by().all.assert_called_once()

    def test_get_foil_hole_info(self):
        return_value = self.test_api.get_foil_hole_info(
            foil_hole_name="test_hole",
            exposure_keys=["test_exposure"],
            particle_keys=["test_key"],
            particle_set_keys=["test_set_key"]
        )

        assert type(return_value) == list
        self.test_api.session.query().join().filter().filter.assert_called_once()
        self.test_api.session.query().join().join().filter().filter().order_by.assert_called_once()
        self.test_api.session.query().join().join().join().filter().filter().order_by.assert_called_once()
        self.test_api.session.query().join().filter().filter().all.assert_called_once()
        self.test_api.session.query().join().join().filter().filter().order_by().all.assert_called_once()
        self.test_api.session.query().join().join().join().filter().filter().order_by().all.assert_called_once()

    @mock.patch("smartem.data_model.extract.select")
    def test_get_grid_square_info(self, mock_select):
        mock_select.return_value = mock.MagicMock()
        return_value = self.test_api.get_grid_square_info(
            grid_square_name="test_square",
            exposure_keys=["test_exposure"],
            particle_keys=["test_key"],
            particle_set_keys=["test_set_key"]
        )

        assert type(return_value) == list
        mock_select().select_from().where().where().order_by.assert_called()
        assert mock_select().select_from().where().where().order_by.call_count == 3
        self.test_api.engine.connect.assert_called()
        assert self.test_api.engine.connect.call_count == 3
        self.test_api.engine.connect().__enter__().execute().fetchall.assert_called()
        assert self.test_api.engine.connect().__enter__().execute().fetchall.call_count == 3

    @mock.patch("smartem.data_model.extract.select")
    def test_get_atlas_info(self, mock_select):
        mock_select.return_value = mock.MagicMock()
        return_value = self.test_api.get_atlas_info(
            atlas_id=1,
            exposure_keys=["test_exposure"],
            particle_keys=["test_key"],
            particle_set_keys=["test_set_key"]
        )

        assert type(return_value) == list
        mock_select().select_from().where().where().order_by.assert_called()
        assert mock_select().select_from().where().where().order_by.call_count == 3
        self.test_api.engine.connect.assert_called()
        assert self.test_api.engine.connect.call_count == 3
        self.test_api.engine.connect().__enter__().execute().fetchall.assert_called()
        assert self.test_api.engine.connect().__enter__().execute().fetchall.call_count == 3

    def test_put(self):
        self.test_api.put(entries=[Project])

        self.test_api.engine.connect.assert_called_once()
        self.test_api.engine.connect().__enter__().execute.assert_called_once()
        self.test_api.engine.connect().__enter__().execute().fetchall.assert_called_once()

    def test_delete_project(self):
        self.test_api.delete_project(project="test")

        self.test_api.engine.connect.assert_called_once()
        self.test_api.engine.connect().__enter__().execute.assert_called()
