import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    users_df: pd.DataFrame | None = None
    cvs_df: pd.DataFrame | None = None
    technologies_df: pd.DataFrame | None = None
    languages_df: pd.DataFrame | None = None
    project_experiences_df: pd.DataFrame | None = None
    work_experiences_df: pd.DataFrame | None = None
    certifications_df: pd.DataFrame | None = None
    courses_df: pd.DataFrame | None = None
    educations_df: pd.DataFrame | None = None
    positions_df: pd.DataFrame | None = None
    blogs_df: pd.DataFrame | None = None
    cv_roles_df: pd.DataFrame | None = None
    key_qualifications_df: pd.DataFrame | None = None
    sc_clearance_df: pd.DataFrame | None = None
    availability_df: pd.DataFrame | None = None


def parse_multilang(multilang_pipe_string: object) -> dict:
    if not isinstance(multilang_pipe_string, str) or not multilang_pipe_string.strip():
        return {}
    result = {}
    for part in multilang_pipe_string.split("|"):
        if ":" in part:
            language_code, translation = part.split(":", 1)
            language_code, translation = language_code.strip(), translation.strip()
            if language_code and translation:
                result[language_code] = translation
    return result


def to_iso_date(raw_date_value: object) -> str | None:
    if raw_date_value is None or (isinstance(raw_date_value, float) and pd.isna(raw_date_value)):
        return None
    date_string = str(raw_date_value).strip()
    if not date_string:
        return None
    if "-" in date_string and len(date_string.split("-")[0]) == 4:
        parsed_date = pd.to_datetime(date_string, errors="coerce")
    else:
        parsed_date = pd.to_datetime(date_string, dayfirst=True, errors="coerce")
    return None if pd.isna(parsed_date) else parsed_date.date().isoformat()


def to_integer(value) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def transform(csv_frames: dict[str, pd.DataFrame]) -> TransformResult:
    logger.info("Starting transform step")
    users_dataframe = csv_frames.get("user_report.csv", pd.DataFrame()).copy()
    usage_dataframe = csv_frames.get("usage_report.csv", pd.DataFrame()).copy()

    if not users_dataframe.empty and "Name (multilang)" in users_dataframe.columns:
        users_dataframe["Name (multilang)"] = users_dataframe["Name (multilang)"].map(parse_multilang)
    else:
        users_dataframe["Name (multilang)"] = [{}] * len(users_dataframe)

    if not usage_dataframe.empty and "Nationality (#{lang})" in usage_dataframe.columns:
        nationality_lookup = {
            str(usage_row["CV Partner User ID"]): parse_multilang(usage_row["Nationality (#{lang})"])
            for _, usage_row in usage_dataframe.iterrows()
            if "CV Partner User ID" in usage_row and pd.notna(usage_row["CV Partner User ID"])
        }
        users_dataframe["nationality_multilang"] = users_dataframe["CV Partner User ID"].map(
            lambda user_id: nationality_lookup.get(str(user_id), {})
        )
    else:
        users_dataframe["nationality_multilang"] = [{}] * len(users_dataframe)

    cvs_dataframe = users_dataframe.copy()
    if "Title (#{lang})" in users_dataframe.columns:
        cvs_dataframe["title_multilang"] = users_dataframe["Title (#{lang})"].map(parse_multilang)
    else:
        cvs_dataframe["title_multilang"] = [{}] * len(cvs_dataframe)

    cvs_dataframe["sfia_level"] = users_dataframe.get("SFIA Level", pd.Series([None] * len(users_dataframe))).map(to_integer)
    cvs_dataframe["cpd_level"]  = users_dataframe.get("CPD Level",  pd.Series([None] * len(users_dataframe))).map(to_integer)
    cvs_dataframe["cpd_band"]   = users_dataframe.get("CPD Band",   pd.Series([None] * len(users_dataframe))).astype("string").where(lambda series: series.notna(), None)
    cvs_dataframe["cpd_label"]  = users_dataframe.get("CPD Label",  pd.Series([None] * len(users_dataframe))).astype("string").where(lambda series: series.notna(), None)

    sc_clearance_dataframe = csv_frames.get("sc_clearance.csv", pd.DataFrame()).copy()
    if not sc_clearance_dataframe.empty:
        for column in ("Valid From", "Valid To"):
            if column in sc_clearance_dataframe.columns:
                sc_clearance_dataframe[column] = sc_clearance_dataframe[column].map(to_iso_date)
        logger.info("Processed sc_clearance.csv: %d rows", len(sc_clearance_dataframe))

    availability_dataframe = csv_frames.get("availability_report.csv", pd.DataFrame()).copy()
    logger.info("users rows=%d, cvs rows=%d", len(users_dataframe), len(cvs_dataframe))
    if users_dataframe.empty:
        raise ValueError("users_df is unexpectedly empty")
    if "CV Partner User ID" not in users_dataframe.columns:
        raise ValueError("Missing CV Partner User ID column in users_df")
    if len(users_dataframe) != len(cvs_dataframe):
        raise ValueError("users_df and cvs_df row counts differ")

    if not availability_dataframe.empty and "Date" in availability_dataframe.columns:
        availability_dataframe["Date"] = availability_dataframe["Date"].map(to_iso_date)
        logger.info("Processed availability_report.csv: %d rows", len(availability_dataframe))

    return TransformResult(
        users_df=users_dataframe if not users_dataframe.empty else pd.DataFrame(),
        cvs_df=cvs_dataframe if not cvs_dataframe.empty else pd.DataFrame(),
        technologies_df=csv_frames.get("technologies.csv"),
        languages_df=csv_frames.get("languages.csv"),
        project_experiences_df=csv_frames.get("project_experiences.csv"),
        work_experiences_df=csv_frames.get("work_experiences.csv"),
        certifications_df=csv_frames.get("certifications.csv"),
        courses_df=csv_frames.get("courses.csv"),
        educations_df=csv_frames.get("educations.csv"),
        positions_df=csv_frames.get("positions.csv"),
        blogs_df=csv_frames.get("blogs.csv"),
        cv_roles_df=csv_frames.get("cv_roles.csv"),
        key_qualifications_df=csv_frames.get("key_qualifications.csv"),
        sc_clearance_df=sc_clearance_dataframe if not sc_clearance_dataframe.empty else pd.DataFrame(),
        availability_df=availability_dataframe if not availability_dataframe.empty else pd.DataFrame(),
    )


__all__ = [
    "TransformResult",
    "transform",
    "parse_multilang",
    "to_iso_date",
]
