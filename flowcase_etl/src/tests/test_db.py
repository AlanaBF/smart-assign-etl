"""Tests for flowcase_etl_pipeline.db module."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from flowcase_etl_pipeline.config import DbConfig
from flowcase_etl_pipeline.db import (
    apply_sql_folder,
    create_database_if_missing,
    get_engine,
)


@pytest.fixture
def db_config():
    return DbConfig(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_pass",
        sslmode="require",
    )


class TestCreateDatabaseIfMissing:
    @patch("flowcase_etl_pipeline.db.psycopg2.connect")
    def test_database_exists_no_create(self, mock_connect, db_config):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        # Database exists
        mock_cursor.fetchone.return_value = (1,)

        create_database_if_missing(db_config)

        mock_connect.assert_called_once_with(
            dbname="postgres",
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            sslmode="require",
        )
        mock_cursor.execute.assert_called_once_with(
            "SELECT 1 FROM pg_database WHERE datname = %s", ("test_db",)
        )
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("flowcase_etl_pipeline.db.psycopg2.connect")
    def test_database_missing_creates_it(self, mock_connect, db_config):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        # Database does not exist
        mock_cursor.fetchone.return_value = None

        create_database_if_missing(db_config)

        assert mock_cursor.execute.call_count == 2
        mock_cursor.execute.assert_any_call(
            "SELECT 1 FROM pg_database WHERE datname = %s", ("test_db",)
        )
        mock_cursor.execute.assert_any_call('CREATE DATABASE "test_db"')

    @patch("flowcase_etl_pipeline.db.psycopg2.connect")
    def test_handles_connection_error_gracefully(self, mock_connect, db_config):
        mock_connect.side_effect = Exception("Connection refused")

        # Should not raise
        create_database_if_missing(db_config)


class TestGetEngine:
    @patch("flowcase_etl_pipeline.db.create_engine")
    def test_returns_engine_with_correct_url(self, mock_create_engine, db_config):
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        engine = get_engine(db_config)

        expected_url = (
            "postgresql+psycopg2://test_user:test_pass"
            "@localhost:5432/test_db"
            "?sslmode=require"
        )
        mock_create_engine.assert_called_once_with(expected_url)
        assert engine == mock_engine

    @patch("flowcase_etl_pipeline.db.create_engine")
    def test_includes_sslmode_in_url(self, mock_create_engine):
        config = DbConfig(
            host="db.example.com",
            port=5433,
            database="prod_db",
            user="admin",
            password="s3cret",
            sslmode="verify-full",
        )
        mock_create_engine.return_value = MagicMock()

        get_engine(config)

        call_url = mock_create_engine.call_args[0][0]
        assert "sslmode=verify-full" in call_url


class TestApplySqlFolder:
    def test_with_valid_sql_files(self, tmp_path):
        sql_folder = tmp_path / "sql"
        sql_folder.mkdir()
        (sql_folder / "001_create_tables.sql").write_text("CREATE TABLE t1 (id int);")
        (sql_folder / "002_create_indexes.sql").write_text("CREATE INDEX idx ON t1(id);")

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        apply_sql_folder(mock_engine, sql_folder)

        assert mock_conn.execute.call_count == 2

    def test_with_missing_folder(self, tmp_path):
        sql_folder = tmp_path / "nonexistent"
        mock_engine = MagicMock()

        # Should not raise, just skip
        apply_sql_folder(mock_engine, sql_folder)

        mock_engine.begin.assert_not_called()

    def test_with_empty_folder(self, tmp_path):
        sql_folder = tmp_path / "sql"
        sql_folder.mkdir()
        mock_engine = MagicMock()

        # Should not raise, just skip
        apply_sql_folder(mock_engine, sql_folder)

        mock_engine.begin.assert_not_called()

    def test_files_applied_in_sorted_order(self, tmp_path):
        sql_folder = tmp_path / "sql"
        sql_folder.mkdir()
        (sql_folder / "003_third.sql").write_text("SELECT 3;")
        (sql_folder / "001_first.sql").write_text("SELECT 1;")
        (sql_folder / "002_second.sql").write_text("SELECT 2;")

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        apply_sql_folder(mock_engine, sql_folder)

        calls = mock_conn.execute.call_args_list
        assert len(calls) == 3
        # Verify order via the text clause's text attribute
        assert calls[0][0][0].text == "SELECT 1;"
        assert calls[1][0][0].text == "SELECT 2;"
        assert calls[2][0][0].text == "SELECT 3;"
