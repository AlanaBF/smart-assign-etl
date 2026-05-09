import logging
from pathlib import Path

import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import DbConfig

logger = logging.getLogger(__name__)


def create_database_if_missing(database_config: DbConfig) -> None:
    try:
        connection = psycopg2.connect(
            dbname="postgres",
            user=database_config.user,
            password=database_config.password,
            host=database_config.host,
            port=database_config.port,
            sslmode=database_config.sslmode,
        )
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_config.database,))
        if not cursor.fetchone():
            logger.info("Creating database %s", database_config.database)
            cursor.execute(f'CREATE DATABASE "{database_config.database}"')
        cursor.close()
        connection.close()
    except Exception as error:
        logger.warning("Could not verify/create database (expected on Azure managed DBs): %s", error)


def get_engine(database_config: DbConfig) -> Engine:
    connection_url = (
        f"postgresql+psycopg2://{database_config.user}:{database_config.password}"
        f"@{database_config.host}:{database_config.port}/{database_config.database}"
        f"?sslmode={database_config.sslmode}"
    )
    return create_engine(connection_url)


def apply_sql_folder(engine: Engine, sql_folder: Path) -> None:
    if not sql_folder.exists():
        logger.info("SQL folder %s not found; skipping schema setup.", sql_folder)
        return
    sql_files = sorted(sql_folder.glob("*.sql"))
    if not sql_files:
        logger.info("No .sql files in %s; nothing to apply.", sql_folder)
        return
    with engine.begin() as connection:
        for sql_file_path in sql_files:
            logger.info("Applying %s", sql_file_path.name)
            connection.execute(text(sql_file_path.read_text()))


__all__ = ["create_database_if_missing", "get_engine", "apply_sql_folder"]
