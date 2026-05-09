from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from flowcase_etl_pipeline.config import DbConfig
from flowcase_etl_pipeline.db import apply_sql_folder, create_database_if_missing
from flowcase_etl_pipeline.extract import extract
from flowcase_etl_pipeline.transform import transform
from flowcase_etl_pipeline.load import load

@pytest.mark.integration
def test_etl_end_to_end_with_qtest(tmp_path):
    # Load .env.test from flowcase_etl directory, not from repository root
    env_test_path = Path(__file__).parent.parent.parent.parent / ".env.test"
    load_dotenv(env_test_path)
    
    with patch("flowcase_etl_pipeline.extract.find_latest_quarterly_report_folder") as mock_find:
        qtest_path = Path("etl_pipeline/flowcase_etl/cv_reports/QTEST").resolve()
        mock_find.return_value = qtest_path
        try:
            cfg = DbConfig.from_env()
        except ValueError as exc:
            pytest.skip(f"Integration test skipped: {exc}")
        
        # SAFETY CHECK: Only allow localhost for integration tests
        if cfg.host != 'localhost':
            pytest.skip(f"Integration test skipped: Host is '{cfg.host}' instead of 'localhost'. This prevents accidental production database usage.")
        
        # SAFETY CHECK: Ensure we're using a test database
        if not (cfg.database.endswith('_test') or cfg.database.startswith('test_')):
            pytest.skip(f"Integration test skipped: Database is '{cfg.database}' instead of ending with '_test' or starting with 'test_'. This prevents accidental production database usage.")
            
        create_database_if_missing(cfg)
        engine = create_engine(
            f"postgresql+psycopg2://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}"
        )

        sql_dir_main = Path(__file__).resolve().parents[1] / "sql"
        sql_dir_tests = Path(__file__).resolve().parent
        apply_sql_folder(engine, sql_dir_main)
        apply_sql_folder(engine, sql_dir_tests)

        result = extract({"base_folder": "etl_pipeline/flowcase_etl/cv_reports", "data_source": "fake"})
        tr = transform(result.frames)
        load(tr, engine)

        with engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW cv_search_profile_qtest_mv"))

        with engine.connect() as conn:
            users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            cvs = conn.execute(text("SELECT COUNT(*) FROM cvs")).scalar()

        assert users > 0
        assert cvs > 0
