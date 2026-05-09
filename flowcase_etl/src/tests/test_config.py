"""Tests for flowcase_etl_pipeline.config module."""

import os
from unittest.mock import patch

import pytest

from flowcase_etl_pipeline.config import DbConfig, FlowcaseConfig, Settings


class TestDbConfigFromEnv:
    def test_from_env_with_all_vars_set(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")
        monkeypatch.setenv("PGSSLMODE", "disable")

        config = DbConfig.from_env()

        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "testdb"
        assert config.user == "testuser"
        assert config.password == "testpass"
        assert config.sslmode == "disable"

    def test_from_env_raises_when_vars_missing(self, monkeypatch):
        monkeypatch.delenv("PGHOST", raising=False)
        monkeypatch.delenv("PGPORT", raising=False)
        monkeypatch.delenv("PGDATABASE", raising=False)
        monkeypatch.delenv("PGUSER", raising=False)
        monkeypatch.delenv("PGPASSWORD", raising=False)

        with pytest.raises(ValueError, match="Missing required database environment variables"):
            DbConfig.from_env()

    def test_from_env_raises_for_non_integer_port(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "not_a_number")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")

        with pytest.raises(ValueError, match="PGPORT must be an integer"):
            DbConfig.from_env()

    def test_from_env_reads_sslmode_default(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")
        monkeypatch.delenv("PGSSLMODE", raising=False)

        config = DbConfig.from_env()

        assert config.sslmode == "require"

    def test_from_env_partial_missing_vars(self, monkeypatch):
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.delenv("PGDATABASE", raising=False)
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.delenv("PGPASSWORD", raising=False)

        with pytest.raises(ValueError, match="database.*password"):
            DbConfig.from_env()


class TestSettingsLoad:
    def test_load_fake_data_source(self, monkeypatch):
        monkeypatch.setenv("FLOWCASE_DATA_SOURCE", "fake")
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")
        monkeypatch.delenv("PGSSLMODE", raising=False)

        settings = Settings.load()

        assert settings.data_source == "fake"
        assert settings.flowcase is None
        assert settings.db.host == "localhost"

    def test_load_real_data_source(self, monkeypatch):
        monkeypatch.setenv("FLOWCASE_DATA_SOURCE", "real")
        monkeypatch.setenv("FLOWCASE_SUBDOMAIN", "mycompany")
        monkeypatch.setenv("FLOWCASE_API_TOKEN", "secret-token-123")
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")
        monkeypatch.delenv("FLOWCASE_OFFICE_IDS", raising=False)
        monkeypatch.delenv("FLOWCASE_LANG_PARAMS", raising=False)

        settings = Settings.load()

        assert settings.data_source == "real"
        assert settings.flowcase is not None
        assert settings.flowcase.subdomain == "mycompany"
        assert settings.flowcase.api_token == "secret-token-123"
        assert settings.flowcase.office_ids is None
        assert settings.flowcase.lang_params is None

    def test_load_real_with_office_ids_and_lang_params(self, monkeypatch):
        monkeypatch.setenv("FLOWCASE_DATA_SOURCE", "real")
        monkeypatch.setenv("FLOWCASE_SUBDOMAIN", "mycompany")
        monkeypatch.setenv("FLOWCASE_API_TOKEN", "secret-token-123")
        monkeypatch.setenv("FLOWCASE_OFFICE_IDS", "office1,office2,office3")
        monkeypatch.setenv("FLOWCASE_LANG_PARAMS", "en,no")
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")

        settings = Settings.load()

        assert settings.flowcase.office_ids == ["office1", "office2", "office3"]
        assert settings.flowcase.lang_params == ["en", "no"]

    def test_load_raises_for_invalid_data_source(self, monkeypatch):
        monkeypatch.setenv("FLOWCASE_DATA_SOURCE", "invalid_source")
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")

        with pytest.raises(ValueError, match="Invalid FLOWCASE_DATA_SOURCE"):
            Settings.load()

    def test_load_raises_when_real_mode_missing_credentials(self, monkeypatch):
        monkeypatch.setenv("FLOWCASE_DATA_SOURCE", "real")
        monkeypatch.delenv("FLOWCASE_SUBDOMAIN", raising=False)
        monkeypatch.delenv("FLOWCASE_API_TOKEN", raising=False)
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")

        with pytest.raises(ValueError, match="requires FLOWCASE_SUBDOMAIN and FLOWCASE_API_TOKEN"):
            Settings.load()

    def test_load_defaults_to_fake_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("FLOWCASE_DATA_SOURCE", raising=False)
        monkeypatch.setenv("PGHOST", "localhost")
        monkeypatch.setenv("PGPORT", "5432")
        monkeypatch.setenv("PGDATABASE", "testdb")
        monkeypatch.setenv("PGUSER", "testuser")
        monkeypatch.setenv("PGPASSWORD", "testpass")

        settings = Settings.load()

        assert settings.data_source == "fake"
