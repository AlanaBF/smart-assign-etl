from pathlib import Path

import pandas as pd
import pytest

from flowcase_etl_pipeline.extract import (
    ExtractResult,
    extract,
    find_latest_quarterly_report_folder,
    load_csv_files_from_folder,
)


def test_find_latest_quarterly_report_folder_picks_latest(tmp_path):
    (tmp_path / "Q12024").mkdir()
    (tmp_path / "Q42023").mkdir()
    (tmp_path / "notes").mkdir()

    latest = find_latest_quarterly_report_folder(tmp_path)
    assert latest.name == "Q12024"


def test_find_latest_quarterly_report_folder_raises_when_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_latest_quarterly_report_folder(tmp_path)


def test_load_csv_files_from_folder_reads_all(tmp_path):
    folder = tmp_path / "Q12024"
    folder.mkdir()
    df = pd.DataFrame({"a": [1, 2]})
    df.to_csv(folder / "sample.csv", index=False)

    frames = load_csv_files_from_folder(folder)
    assert list(frames.keys()) == ["sample.csv"]
    assert frames["sample.csv"].shape == (2, 1)


def test_extract_returns_latest_folder_and_frames(tmp_path):
    old = tmp_path / "Q12024"
    new = tmp_path / "Q22024"
    old.mkdir()
    new.mkdir()
    pd.DataFrame({"col": [1]}).to_csv(new / "user_report.csv", index=False)

    result = extract({"base_folder": tmp_path, "data_source": "fake"})

    assert isinstance(result, ExtractResult)
    assert result.data_dir == new
    assert "user_report.csv" in result.frames


def test_extract_real_mode_returns_empty():
    result = extract({"data_source": "real"})
    assert isinstance(result, ExtractResult)
    assert result.frames == {}

def test_find_latest_quarterly_report_folder_no_candidates(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_latest_quarterly_report_folder(tmp_path)

def test_extract_real_mode_returns_placeholder():
    result = extract({"data_source": "real"})
    assert getattr(result, "data_dir", None) == Path(".")
    assert getattr(result, "frames", {}) == {}
