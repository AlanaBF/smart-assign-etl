import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExtractResult:
    data_dir: Path
    frames: dict[str, pd.DataFrame]


def find_latest_quarterly_report_folder(base_folder="cv_reports"):
    logger.info("Finding the latest quarterly report folder")
    base_path = Path(base_folder)

    quarterly_pattern = re.compile(r"Q([1-4])(\d{4})")
    candidates = []
    for folder in base_path.iterdir():
        if not folder.is_dir():
            continue
        match = quarterly_pattern.match(folder.name)
        if match:
            quarter = int(match.group(1))
            year = int(match.group(2))
            candidates.append((year, quarter, folder))

    if not candidates:
        raise FileNotFoundError(f"No quarterly report folders found in {base_path}.")

    latest_year, latest_quarter, latest_folder = max(
        candidates, key=lambda folder_entry: (folder_entry[0], folder_entry[1])
    )
    logger.info("Quarterly folders: %s", sorted(folder.name for _, _, folder in candidates))
    logger.info("Using: %s (Q%d %d)", latest_folder.name, latest_quarter, latest_year)
    return latest_folder


def load_csv_files_from_folder(report_folder: Path) -> dict[str, pd.DataFrame]:
    csv_files = list(Path(report_folder).glob("*.csv"))
    logger.info("Found %d CSV files in %s", len(csv_files), report_folder)
    dataframes: dict[str, pd.DataFrame] = {}
    for csv_file in csv_files:
        try:
            dataframe = pd.read_csv(csv_file)
            dataframes[csv_file.name] = dataframe
            logger.info("Loaded %s -> %s", csv_file.name, dataframe.shape)
        except Exception as error:
            logger.warning("Failed to read %s: %s", csv_file.name, error)
    return dataframes


def extract(settings: dict) -> ExtractResult:
    data_source = settings.get("data_source", "fake")
    if data_source == "real":
        logger.info("[extract] Real data mode selected, not implemented yet.")
        return ExtractResult(data_dir=Path("."), frames={})

    base_folder = settings.get("base_folder", "cv_reports")
    data_dir = find_latest_quarterly_report_folder(base_folder)
    frames = load_csv_files_from_folder(data_dir)
    logger.info("Extracted %d CSV files from %s", len(frames), data_dir)
    return ExtractResult(data_dir=data_dir, frames=frames)


__all__ = [
    "ExtractResult",
    "extract",
    "find_latest_quarterly_report_folder",
    "load_csv_files_from_folder",
]
