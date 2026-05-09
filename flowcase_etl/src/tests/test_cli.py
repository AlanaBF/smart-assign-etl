"""Tests for flowcase_etl_pipeline.cli module."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from flowcase_etl_pipeline.cli import build_parser, run_etl, main


@pytest.fixture
def mock_settings_fake():
    """Settings configured for fake data source."""
    settings = MagicMock()
    settings.data_source = "fake"
    settings.cv_reports_dir = Path("/tmp/cv_reports")
    settings.sql_dir = Path("/tmp/sql")
    settings.db = MagicMock()
    settings.flowcase = None
    return settings


@pytest.fixture
def mock_settings_real():
    """Settings configured for real data source."""
    settings = MagicMock()
    settings.data_source = "real"
    settings.cv_reports_dir = Path("/tmp/cv_reports")
    settings.sql_dir = Path("/tmp/sql")
    settings.db = MagicMock()
    settings.flowcase = MagicMock()
    return settings


class TestBuildParser:
    def test_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.generate_fake is False
        assert args.data_folder is None
        assert args.sql_folder is None
        assert args.skip_refresh is False

    def test_generate_fake_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--generate-fake"])
        assert args.generate_fake is True

    def test_skip_refresh_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--skip-refresh"])
        assert args.skip_refresh is True

    def test_data_folder_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--data-folder", "/some/path"])
        assert args.data_folder == "/some/path"

    def test_sql_folder_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--sql-folder", "/sql/path"])
        assert args.sql_folder == "/sql/path"


class TestRunEtlFakeSource:
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    @patch("flowcase_etl_pipeline.cli.fake_data")
    def test_run_etl_fake_generate(
        self,
        mock_fake_data,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_settings_fake,
    ):
        mock_settings_cls.load.return_value = mock_settings_fake

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {"users": MagicMock()}
        mock_extract.return_value = mock_extract_result

        mock_transform_result = MagicMock()
        mock_transform.return_value = mock_transform_result

        # Mock engine.begin and engine.connect context managers for KPI + MV
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 10
        mock_conn.execute.return_value.fetchall.return_value = [("Python", 5)]
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        run_etl(generate_fake=True, refresh_mv=True, data_folder=None, sql_folder=None)

        mock_fake_data.main.assert_called_once()
        mock_create_db.assert_called_once_with(mock_settings_fake.db)
        mock_get_engine.assert_called_once_with(mock_settings_fake.db)
        mock_apply_sql.assert_called_once_with(mock_engine, mock_settings_fake.sql_dir)
        mock_extract.assert_called_once()
        mock_transform.assert_called_once_with(mock_extract_result.frames)
        mock_load.assert_called_once_with(mock_transform_result, mock_engine)

    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    @patch("flowcase_etl_pipeline.cli.fake_data")
    def test_run_etl_fake_no_generate_reuses_existing(
        self,
        mock_fake_data,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_settings_fake,
    ):
        mock_settings_cls.load.return_value = mock_settings_fake

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {}
        mock_extract.return_value = mock_extract_result
        mock_transform.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 5
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        run_etl(generate_fake=False, refresh_mv=True, data_folder=None, sql_folder=None)

        mock_fake_data.main.assert_not_called()


class TestRunEtlRealSource:
    @patch("flowcase_etl_pipeline.cli.FlowcaseClient")
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    def test_run_etl_real_source(
        self,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_flowcase_client_cls,
        mock_settings_real,
    ):
        mock_settings_cls.load.return_value = mock_settings_real

        mock_client = MagicMock()
        mock_flowcase_client_cls.return_value = mock_client

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {}
        mock_extract.return_value = mock_extract_result
        mock_transform.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 10
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        run_etl(generate_fake=False, refresh_mv=True, data_folder=None, sql_folder=None)

        mock_flowcase_client_cls.assert_called_once_with(mock_settings_real.flowcase)
        mock_client.fetch_all_reports.assert_called_once()

    @patch("flowcase_etl_pipeline.cli.FlowcaseClient")
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    def test_run_etl_real_source_missing_flowcase_config(
        self,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_flowcase_client_cls,
    ):
        settings = MagicMock()
        settings.data_source = "real"
        settings.flowcase = None
        settings.cv_reports_dir = Path("/tmp/cv_reports")
        settings.sql_dir = Path("/tmp/sql")
        mock_settings_cls.load.return_value = settings

        with pytest.raises(RuntimeError, match="Flowcase config is missing"):
            run_etl(generate_fake=False, refresh_mv=True, data_folder=None, sql_folder=None)


class TestRunEtlSkipRefresh:
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    @patch("flowcase_etl_pipeline.cli.fake_data")
    def test_skip_refresh_does_not_call_begin(
        self,
        mock_fake_data,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_settings_fake,
    ):
        mock_settings_cls.load.return_value = mock_settings_fake

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {}
        mock_extract.return_value = mock_extract_result
        mock_transform.return_value = MagicMock()

        # Only connect (KPI) should be called, not begin (MV refresh)
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 5
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        run_etl(generate_fake=True, refresh_mv=False, data_folder=None, sql_folder=None)

        mock_engine.begin.assert_not_called()


class TestRunEtlKpiLogging:
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    @patch("flowcase_etl_pipeline.cli.fake_data")
    def test_kpi_query_failure_is_handled_gracefully(
        self,
        mock_fake_data,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_settings_fake,
    ):
        mock_settings_cls.load.return_value = mock_settings_fake

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {}
        mock_extract.return_value = mock_extract_result
        mock_transform.return_value = MagicMock()

        # Make connect raise an error to test KPI failure path
        mock_engine.connect.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB error")
        )
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        # Should not raise - just log warning
        run_etl(generate_fake=True, refresh_mv=False, data_folder=None, sql_folder=None)


class TestRunEtlCustomFolders:
    @patch("flowcase_etl_pipeline.cli.Settings")
    @patch("flowcase_etl_pipeline.cli.create_database_if_missing")
    @patch("flowcase_etl_pipeline.cli.get_engine")
    @patch("flowcase_etl_pipeline.cli.apply_sql_folder")
    @patch("flowcase_etl_pipeline.cli.extract")
    @patch("flowcase_etl_pipeline.cli.transform")
    @patch("flowcase_etl_pipeline.cli.load")
    @patch("flowcase_etl_pipeline.cli.fake_data")
    def test_custom_data_and_sql_folders(
        self,
        mock_fake_data,
        mock_load,
        mock_transform,
        mock_extract,
        mock_apply_sql,
        mock_get_engine,
        mock_create_db,
        mock_settings_cls,
        mock_settings_fake,
    ):
        mock_settings_cls.load.return_value = mock_settings_fake

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_extract_result = MagicMock()
        mock_extract_result.frames = {}
        mock_extract.return_value = mock_extract_result
        mock_transform.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 0
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        custom_data = Path("/custom/data")
        custom_sql = Path("/custom/sql")

        run_etl(
            generate_fake=True,
            refresh_mv=False,
            data_folder=custom_data,
            sql_folder=custom_sql,
        )

        # Verify custom folders are used instead of settings defaults
        mock_apply_sql.assert_called_once_with(mock_engine, custom_sql)
        extract_call = mock_extract.call_args[0][0]
        assert extract_call["base_folder"] == custom_data


class TestMain:
    @patch("flowcase_etl_pipeline.cli.run_etl")
    @patch("flowcase_etl_pipeline.cli.build_parser")
    def test_main_calls_run_etl(self, mock_build_parser, mock_run_etl):
        mock_parser = MagicMock()
        mock_build_parser.return_value = mock_parser
        mock_args = MagicMock()
        mock_args.generate_fake = True
        mock_args.skip_refresh = False
        mock_args.data_folder = None
        mock_args.sql_folder = None
        mock_parser.parse_args.return_value = mock_args

        main()

        mock_run_etl.assert_called_once_with(
            generate_fake=True,
            refresh_mv=True,
            data_folder=None,
            sql_folder=None,
        )

    @patch("flowcase_etl_pipeline.cli.run_etl")
    @patch("flowcase_etl_pipeline.cli.build_parser")
    def test_main_with_data_folder(self, mock_build_parser, mock_run_etl):
        mock_parser = MagicMock()
        mock_build_parser.return_value = mock_parser
        mock_args = MagicMock()
        mock_args.generate_fake = False
        mock_args.skip_refresh = True
        mock_args.data_folder = "/some/folder"
        mock_args.sql_folder = None
        mock_parser.parse_args.return_value = mock_args

        main()

        mock_run_etl.assert_called_once_with(
            generate_fake=False,
            refresh_mv=False,
            data_folder=Path("/some/folder"),
            sql_folder=None,
        )
