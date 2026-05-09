import json
import logging
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .constants import (
    CV_PARTNER_USER_ID, CV_PARTNER_CV_ID, CV_PARTNER_SECTION_ID,
    NAME_MULTILANG, EMAIL, UPN, EXTERNAL_USER_ID, PHONE_NUMBER,
    LANDLINE, BIRTH_YEAR, DEPARTMENT, COUNTRY, USER_CREATED_AT,
    YEARS_OF_EDUCATION, YEARS_SINCE_FIRST_WORK_EXPERIENCE, HAS_PROFILE_IMAGE,
    OWNS_A_REFERENCE_PROJECT, READ_AND_UNDERSTOOD_PRIVACY_NOTICE,
    CV_LAST_UPDATED_BY_OWNER, CV_LAST_UPDATED, EXTERNAL_UNIQUE_ID,
    MONTH_FROM, YEAR_FROM, MONTH_TO, YEAR_TO, MONTH, YEAR,
    MONTH_EXPIRE, YEAR_EXPIRE, HIGHLIGHTED, NAME, DESCRIPTION,
    LONG_DESCRIPTION, UPDATED, UPDATED_BY_OWNER, EMPLOYER,
    ATTACHMENTS, PLACE_OF_STUDY, DEGREE, ORGANISER, LABEL,
    SUMMARY_OF_QUALIFICATIONS, SHORT_DESCRIPTION, SKILL_NAME,
    YEAR_EXPERIENCE, PROFICIENCY_0_5, LANGUAGE, LEVEL,
    CUSTOMER_INT, CUSTOMER_MULTILANG, CUSTOMER_ANONYMOUS_INT,
    CUSTOMER_ANONYMOUS_MULTILANG, DESCRIPTION_INT, DESCRIPTION_MULTILANG,
    LONG_DESCRIPTION_INT, LONG_DESCRIPTION_MULTILANG, INDUSTRY,
    PROJECT_TYPE, PERCENT_ALLOCATED, EXTENT_INDIVIDUAL_HOURS,
    EXTENT_HOURS, EXTENT_TOTAL_HOURS, EXTENT_UNIT, EXTENT_CURRENCY,
    EXTENT_TOTAL, EXTENT_TOTAL_CURRENCY, PROJECT_AREA, PROJECT_AREA_UNIT,
    CLEARANCE, VALID_FROM, VALID_TO, VERIFIED_BY, NOTES, DATE,
    PERCENT_AVAILABLE, SOURCE, IS_OFFICIAL_MASTERDATA, DEFAULT_SOURCE,
    DEFAULT_CLEARANCE, DEFAULT_DATE, NAME_FIELD
)

logger = logging.getLogger(__name__)


def _is_null(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value))


def _parse_boolean(value):
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "t", "yes", "y")


def _normalize_string(value, default=""):
    if _is_null(value):
        return default
    text_value = str(value).strip()
    return text_value if text_value else default


def _parse_date(value, default=None):
    if _is_null(value) or str(value).strip() == "":
        return default
    text_value = str(value).strip()
    is_iso_format = len(text_value) == 10 and text_value[4] == "-"
    parsed = pd.to_datetime(text_value, dayfirst=not is_iso_format, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _lookup_user_id(conn, email=None, upn=None, external_id=None):
    if email:
        uid = conn.execute(text("SELECT user_id FROM users WHERE lower(email)=lower(:e)"), {"e": email}).scalar()
        if uid:
            return uid
    if upn:
        uid = conn.execute(text("SELECT user_id FROM users WHERE lower(upn)=lower(:u)"), {"u": upn}).scalar()
        if uid:
            return uid
    if external_id:
        uid = conn.execute(text("SELECT user_id FROM users WHERE external_user_id=:x"), {"x": external_id}).scalar()
        if uid:
            return uid
    return None


def _get_cv_id(conn, cv_partner_cv_id: str):
    return conn.execute(
        text("SELECT cv_id FROM cvs WHERE cv_partner_cv_id=:cid"),
        {"cid": str(cv_partner_cv_id)},
    ).scalar()


ALLOWED_DIMENSION_TABLES = {"dim_technology", "dim_language", "dim_industry", "dim_project_type", "dim_clearance"}


def _ensure_dimension_exists(conn, table: str, name: Optional[str], key: str = NAME_FIELD, id_col: str = None):
    if not name:
        return None
    if table not in ALLOWED_DIMENSION_TABLES:
        raise ValueError(f"Invalid dimension table: {table}")
    if id_col is None:
        id_col = (table[4:] + "_id") if table.startswith("dim_") else (table.rstrip("s") + "_id")
    conn.execute(text(f"INSERT INTO {table} ({key}) VALUES (:n) ON CONFLICT ({key}) DO NOTHING"), {"n": name})
    return conn.execute(text(f"SELECT {id_col} FROM {table} WHERE {key}=:n"), {"n": name}).scalar()

def upsert_users(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} users.")
    sql = text(
        """
        INSERT INTO users
          (cv_partner_user_id, name_multilang, email, upn, external_user_id,
           phone_number, landline, birth_year, department, country,
           user_created_at, nationality_multilang)
        VALUES
          (:cv_partner_user_id, CAST(:name_multilang AS JSONB), :email, :upn, :external_user_id,
           :phone_number, :landline, :birth_year, :department, :country,
           :user_created_at, CAST(:nationality_multilang AS JSONB))
        ON CONFLICT (cv_partner_user_id) DO UPDATE
        SET name_multilang = EXCLUDED.name_multilang,
            email = EXCLUDED.email,
            upn = EXCLUDED.upn,
            external_user_id = EXCLUDED.external_user_id,
            phone_number = EXCLUDED.phone_number,
            landline = EXCLUDED.landline,
            birth_year = EXCLUDED.birth_year,
            department = EXCLUDED.department,
            country = EXCLUDED.country,
            user_created_at = EXCLUDED.user_created_at,
            nationality_multilang = EXCLUDED.nationality_multilang
    """
    )
    
    payload = []
    for _, row in df.iterrows():
        payload.append(
            {
                "cv_partner_user_id": str(row[CV_PARTNER_USER_ID]),
                "name_multilang": json.dumps(row[NAME_MULTILANG]),
                "email": row.get(EMAIL),
                "upn": row.get(UPN),
                "external_user_id": row.get(EXTERNAL_USER_ID),
                "phone_number": row.get(PHONE_NUMBER),
                "landline": row.get(LANDLINE),
                "birth_year": int(row[BIRTH_YEAR]) if pd.notna(row.get(BIRTH_YEAR)) else None,
                "department": row.get(DEPARTMENT),
                "country": row.get(COUNTRY),
                "user_created_at": row.get(USER_CREATED_AT),
                "nationality_multilang": json.dumps(row.get("nationality_multilang", {})),
            },
        )
    if payload:
        conn.execute(sql, payload)


def upsert_cvs(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} CVs...")
    sql = text(
        """
        INSERT INTO cvs
          (cv_partner_cv_id, user_id, title_multilang, years_of_education,
           years_since_first_work_experience, has_profile_image,
           owns_reference_project, read_privacy_notice,
           cv_last_updated_by_owner, cv_last_updated,
           sfia_level, cpd_level, cpd_band, cpd_label)
        VALUES
          (:cv_partner_cv_id, :user_id, CAST(:title_multilang AS JSONB), :yoe, :ysfwe,
           :has_img, :owns_ref, :read_priv, :lu_owner, :lu,
           :sfia_level, :cpd_level, :cpd_band, :cpd_label)
        ON CONFLICT (cv_partner_cv_id) DO UPDATE
        SET title_multilang = EXCLUDED.title_multilang,
            years_of_education = EXCLUDED.years_of_education,
            years_since_first_work_experience = EXCLUDED.years_since_first_work_experience,
            has_profile_image = EXCLUDED.has_profile_image,
            owns_reference_project = EXCLUDED.owns_reference_project,
            read_privacy_notice = EXCLUDED.read_privacy_notice,
            cv_last_updated_by_owner = EXCLUDED.cv_last_updated_by_owner,
            cv_last_updated = EXCLUDED.cv_last_updated,
            sfia_level = EXCLUDED.sfia_level,
            cpd_level  = EXCLUDED.cpd_level,
            cpd_band   = EXCLUDED.cpd_band,
            cpd_label  = EXCLUDED.cpd_label
    """
    )
    payload = []
    for _, row in df.iterrows():
        uid = conn.execute(
            text("SELECT user_id FROM users WHERE cv_partner_user_id=:uid"),
            {"uid": str(row[CV_PARTNER_USER_ID])},
        ).scalar()
        if uid is None:
            logger.warning(f"Skipping CV {row[CV_PARTNER_CV_ID]} (unknown user {row[CV_PARTNER_USER_ID]})")
            continue

        payload.append(
            {
                "cv_partner_cv_id": str(row[CV_PARTNER_CV_ID]),
                "user_id": uid,
                "title_multilang": json.dumps(row["title_multilang"]),
                "yoe": int(row[YEARS_OF_EDUCATION]) if pd.notna(row[YEARS_OF_EDUCATION]) else None,
                "ysfwe": int(row[YEARS_SINCE_FIRST_WORK_EXPERIENCE]) if pd.notna(row[YEARS_SINCE_FIRST_WORK_EXPERIENCE]) else None,
                "has_img": _parse_boolean(row[HAS_PROFILE_IMAGE]),
                "owns_ref": _parse_boolean(row[OWNS_A_REFERENCE_PROJECT]),
                "read_priv": _parse_boolean(row[READ_AND_UNDERSTOOD_PRIVACY_NOTICE]),
                "lu_owner": row[CV_LAST_UPDATED_BY_OWNER],
                "lu": row[CV_LAST_UPDATED],
                "sfia_level": row.get("sfia_level"),
                "cpd_level": row.get("cpd_level"),
                "cpd_band": None if pd.isna(row.get("cpd_band")) else str(row.get("cpd_band")),
                "cpd_label": None if pd.isna(row.get("cpd_label")) else str(row.get("cpd_label")),
            },
        )
    if payload:
        conn.execute(sql, payload)


def upsert_technologies(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} technologies...")
    
    
    insert_dim_sql = text(
        """
        INSERT INTO dim_technology (name)
        VALUES (:name)
        ON CONFLICT (name) DO NOTHING
        """
    )

    insert_link_sql = text(
        """
        INSERT INTO cv_technology (
            cv_id,
            technology_id,
            years_experience,
            proficiency,
            is_official_masterdata
        )
        VALUES (
            :cv,
            :tech,
            :yexp,
            :prof,
            CAST(:is_md AS JSONB)
        )
        ON CONFLICT (cv_id, technology_id) DO UPDATE
        SET years_experience      = EXCLUDED.years_experience,
            proficiency           = EXCLUDED.proficiency,
            is_official_masterdata = EXCLUDED.is_official_masterdata
        """
    )
    link_payload = []

    for _, row in df.iterrows():
        tech_name = row[SKILL_NAME]

        conn.execute(insert_dim_sql, {"name": tech_name})

        tech_id = conn.execute(
            text("SELECT technology_id FROM dim_technology WHERE name = :n"),
            {"n": tech_name},
        ).scalar()

        if tech_id is None:
            logger.warning(f"Skipping tech link; cannot resolve technology '{tech_name}'")
            continue

        cv_id = conn.execute(
            text("SELECT cv_id FROM cvs WHERE cv_partner_cv_id = :cid"),
            {"cid": str(row[CV_PARTNER_CV_ID])},
        ).scalar()

        if cv_id is None:
            logger.warning(f"Skipping tech link; unknown CV {row[CV_PARTNER_CV_ID]}")
            continue

        link_payload.append(
            {
                "cv": cv_id,
                "tech": tech_id,
                "yexp": int(row[YEAR_EXPERIENCE]) if pd.notna(row[YEAR_EXPERIENCE]) else None,
                "prof": int(row[PROFICIENCY_0_5]) if pd.notna(row[PROFICIENCY_0_5]) else None,
                "is_md": json.dumps(row[IS_OFFICIAL_MASTERDATA]),
            }
        )

    if link_payload:
        conn.execute(insert_link_sql, link_payload)

def upsert_languages(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} languages...")
    sql = text(
        """
        INSERT INTO cv_language
          (cv_id, language_id, level, highlighted, is_official_masterdata, updated, updated_by_owner)
        VALUES
          (:cv_id, :lang_id, :level, :highlighted, CAST(:is_md AS JSONB), :updated, :updated_by_owner)
        ON CONFLICT (cv_id, language_id) DO UPDATE
        SET level = EXCLUDED.level,
            highlighted = EXCLUDED.highlighted,
            is_official_masterdata = EXCLUDED.is_official_masterdata,
            updated = EXCLUDED.updated,
            updated_by_owner = EXCLUDED.updated_by_owner
    """
    )
    payload = []
    for _, row in df.iterrows():
        cv_id = _get_cv_id(conn, row[CV_PARTNER_CV_ID])
        if not cv_id:
            continue
        lang_id = _ensure_dimension_exists(conn, "dim_language", row.get(LANGUAGE))
        payload.append(
            {
                "cv_id": cv_id,
                "lang_id": lang_id,
                "level": row.get(LEVEL),
                "highlighted": _parse_boolean(row.get(HIGHLIGHTED)),
                "is_md": json.dumps(row.get(IS_OFFICIAL_MASTERDATA, {})),
                "updated": row.get(UPDATED),
                "updated_by_owner": row.get(UPDATED_BY_OWNER),
            },
        )
    if payload:
        conn.execute(sql, payload)


def upsert_project_experiences(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} project experiences...")
    sql = text(
        """
      INSERT INTO project_experience
        (cv_id, cv_partner_section_id, external_unique_id,
         month_from, year_from, month_to, year_to,
         customer_int, customer_multilang,
         customer_anon_int, customer_anon_multilang,
         description_int, description_multilang,
         long_description_int, long_description_multilang,
         industry_id, project_type_id,
         percent_allocated, extent_individual_hours, extent_hours, extent_total_hours,
         extent_unit, extent_currency, extent_total, extent_total_currency,
         project_area, project_area_unit,
         highlighted, updated, updated_by_owner)
      VALUES
        (:cv_id, :sid, :ext_id,
         :m_from, :y_from, :m_to, :y_to,
         :cust_int, CAST(:cust_ml AS JSONB),
         :cust_anon_int, CAST(:cust_anon_ml AS JSONB),
         :desc_int, CAST(:desc_ml AS JSONB),
         :ldesc_int, CAST(:ldesc_ml AS JSONB),
         :industry_id, :project_type_id,
         :pct_alloc, :indiv_hours, :hours, :total_hours,
         :extent_unit, :extent_curr, :extent_total, :extent_total_curr,
         :proj_area, :proj_area_unit,
         :highlighted, :updated, :updated_by_owner)
      ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
      SET external_unique_id = EXCLUDED.external_unique_id,
          month_from = EXCLUDED.month_from, year_from = EXCLUDED.year_from,
          month_to = EXCLUDED.month_to, year_to = EXCLUDED.year_to,
          customer_int = EXCLUDED.customer_int, customer_multilang = EXCLUDED.customer_multilang,
          customer_anon_int = EXCLUDED.customer_anon_int, customer_anon_multilang = EXCLUDED.customer_anon_multilang,
          description_int = EXCLUDED.description_int, description_multilang = EXCLUDED.description_multilang,
          long_description_int = EXCLUDED.long_description_int, long_description_multilang = EXCLUDED.long_description_multilang,
          industry_id = EXCLUDED.industry_id, project_type_id = EXCLUDED.project_type_id,
          percent_allocated = EXCLUDED.percent_allocated, extent_individual_hours = EXCLUDED.extent_individual_hours,
          extent_hours = EXCLUDED.extent_hours, extent_total_hours = EXCLUDED.extent_total_hours,
          extent_unit = EXCLUDED.extent_unit, extent_currency = EXCLUDED.extent_currency,
          extent_total = EXCLUDED.extent_total, extent_total_currency = EXCLUDED.extent_total_currency,
          project_area = EXCLUDED.project_area, project_area_unit = EXCLUDED.project_area_unit,
          highlighted = EXCLUDED.highlighted, updated = EXCLUDED.updated,
          updated_by_owner = EXCLUDED.updated_by_owner
    """
    )
    payload = []
    for _, row in df.iterrows():
        cv_id = _get_cv_id(conn, row[CV_PARTNER_CV_ID])
        if not cv_id:
            continue
        payload.append(
            {
                "cv_id": cv_id,
                "sid": row.get(CV_PARTNER_SECTION_ID),
                "ext_id": row.get(EXTERNAL_UNIQUE_ID),
                "m_from": row.get(MONTH_FROM),
                "y_from": row.get(YEAR_FROM),
                "m_to": row.get(MONTH_TO),
                "y_to": row.get(YEAR_TO),
                "cust_int": row.get(CUSTOMER_INT),
                "cust_ml": json.dumps(row.get(CUSTOMER_MULTILANG, {})),
                "cust_anon_int": row.get(CUSTOMER_ANONYMOUS_INT),
                "cust_anon_ml": json.dumps(row.get(CUSTOMER_ANONYMOUS_MULTILANG, {})),
                "desc_int": row.get(DESCRIPTION_INT),
                "desc_ml": json.dumps(row.get(DESCRIPTION_MULTILANG, {})),
                "ldesc_int": row.get(LONG_DESCRIPTION_INT),
                "ldesc_ml": json.dumps(row.get(LONG_DESCRIPTION_MULTILANG, {})),
                "industry_id": _ensure_dimension_exists(conn, "dim_industry", row.get(INDUSTRY)),
                "project_type_id": _ensure_dimension_exists(conn, "dim_project_type", row.get(PROJECT_TYPE)),
                "pct_alloc": row.get(PERCENT_ALLOCATED),
                "indiv_hours": row.get(EXTENT_INDIVIDUAL_HOURS),
                "hours": row.get(EXTENT_HOURS),
                "total_hours": row.get(EXTENT_TOTAL_HOURS),
                "extent_unit": row.get(EXTENT_UNIT),
                "extent_curr": row.get(EXTENT_CURRENCY),
                "extent_total": row.get(EXTENT_TOTAL),
                "extent_total_curr": row.get(EXTENT_TOTAL_CURRENCY),
                "proj_area": row.get(PROJECT_AREA),
                "proj_area_unit": row.get(PROJECT_AREA_UNIT),
                "highlighted": _parse_boolean(row.get(HIGHLIGHTED)),
                "updated": row.get(UPDATED),
                "updated_by_owner": row.get(UPDATED_BY_OWNER),
            },
        )
    if payload:
        conn.execute(sql, payload)


def upsert_section(conn, df: pd.DataFrame, sql: str, fields: dict):
    if df is None or df.empty:
        return
    payload = []
    for _, row in df.iterrows():
        cv_id = _get_cv_id(conn, row["CV Partner CV ID"])
        if cv_id is None:
            continue
        item = {db_col: row.get(csv_col) for db_col, csv_col in fields.items()}
        item["cv_id"] = cv_id
        payload.append(item)
    if payload:
        logger.info(f"Upserting {len(payload)} rows.")
        conn.execute(text(sql), payload)


WORK_EXPERIENCE_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "month_from": MONTH_FROM,
    "year_from": YEAR_FROM,
    "month_to": MONTH_TO,
    "year_to": YEAR_TO,
    "highlighted": HIGHLIGHTED,
    "employer": EMPLOYER,
    "description": DESCRIPTION,
    "long_description": LONG_DESCRIPTION,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
WORK_EXPERIENCE_SQL = """
    INSERT INTO work_experience (cv_id, cv_partner_section_id, external_unique_id, month_from, year_from, month_to, year_to, highlighted, employer, description, long_description, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :month_from, :year_from, :month_to, :year_to, :highlighted, :employer, :description, :long_description, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, month_from=EXCLUDED.month_from, year_from=EXCLUDED.year_from, month_to=EXCLUDED.month_to, year_to=EXCLUDED.year_to, highlighted=EXCLUDED.highlighted, employer=EXCLUDED.employer, description=EXCLUDED.description, long_description=EXCLUDED.long_description, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_work_experiences(conn, df: pd.DataFrame):
    upsert_section(conn, df, WORK_EXPERIENCE_SQL, WORK_EXPERIENCE_FIELDS)


CERTIFICATION_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "month": MONTH,
    "year": YEAR,
    "month_expire": MONTH_EXPIRE,
    "year_expire": YEAR_EXPIRE,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
CERTIFICATION_SQL = """
    INSERT INTO certification (cv_id, cv_partner_section_id, external_unique_id, month, year, month_expire, year_expire, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :month, :year, :month_expire, :year_expire, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, month=EXCLUDED.month, year=EXCLUDED.year, month_expire=EXCLUDED.month_expire, year_expire=EXCLUDED.year_expire, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_certifications(conn, df: pd.DataFrame):
    upsert_section(conn, df, CERTIFICATION_SQL, CERTIFICATION_FIELDS)


def upsert_courses(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} rows into course...")
    sql = text(
        """
        INSERT INTO course
          (cv_id, cv_partner_section_id, external_unique_id,
           month, year, name, organiser, long_description,
           highlighted, is_official_masterdata, attachments,
           updated, updated_by_owner)
        VALUES
          (:cv_id, :cv_partner_section_id, :external_unique_id,
           :month, :year, :name, :organiser, :long_description,
           :highlighted, CAST(:is_official_masterdata AS JSONB), :attachments,
           :updated, :updated_by_owner)
        ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
        SET external_unique_id     = EXCLUDED.external_unique_id,
            month                  = EXCLUDED.month,
            year                   = EXCLUDED.year,
            name                   = EXCLUDED.name,
            organiser              = EXCLUDED.organiser,
            long_description       = EXCLUDED.long_description,
            highlighted            = EXCLUDED.highlighted,
            is_official_masterdata = EXCLUDED.is_official_masterdata,
            attachments            = EXCLUDED.attachments,
            updated                = EXCLUDED.updated,
            updated_by_owner       = EXCLUDED.updated_by_owner
        """
    )
    payload = []
    for _, row in df.iterrows():
        cv_id = _get_cv_id(conn, row[CV_PARTNER_CV_ID])
        if cv_id is None:
            continue
        payload.append(
            {
                "cv_id": cv_id,
                "cv_partner_section_id": row.get(CV_PARTNER_SECTION_ID),
                "external_unique_id": row.get(EXTERNAL_UNIQUE_ID),
                "month": row.get(MONTH),
                "year": row.get(YEAR),
                "name": row.get(NAME),
                "organiser": row.get(ORGANISER),
                "long_description": row.get(LONG_DESCRIPTION),
                "highlighted": _parse_boolean(row.get(HIGHLIGHTED)),
                "is_official_masterdata": json.dumps(row.get(IS_OFFICIAL_MASTERDATA, {})),
                "attachments": _normalize_string(row.get(ATTACHMENTS), None),
                "updated": row.get(UPDATED),
                "updated_by_owner": row.get(UPDATED_BY_OWNER),
            }
        )
    if payload:
        conn.execute(sql, payload)


EDUCATION_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "month_from": MONTH_FROM,
    "year_from": YEAR_FROM,
    "month_to": MONTH_TO,
    "year_to": YEAR_TO,
    "highlighted": HIGHLIGHTED,
    "attachments": ATTACHMENTS,
    "place_of_study": PLACE_OF_STUDY,
    "degree": DEGREE,
    "description": DESCRIPTION,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
EDUCATION_SQL = """
    INSERT INTO education (cv_id, cv_partner_section_id, external_unique_id, month_from, year_from, month_to, year_to, highlighted, attachments, place_of_study, degree, description, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :month_from, :year_from, :month_to, :year_to, :highlighted, :attachments, :place_of_study, :degree, :description, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, month_from=EXCLUDED.month_from, year_from=EXCLUDED.year_from, month_to=EXCLUDED.month_to, year_to=EXCLUDED.year_to, highlighted=EXCLUDED.highlighted, attachments=EXCLUDED.attachments, place_of_study=EXCLUDED.place_of_study, degree=EXCLUDED.degree, description=EXCLUDED.description, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_educations(conn, df: pd.DataFrame):
    upsert_section(conn, df, EDUCATION_SQL, EDUCATION_FIELDS)


POSITION_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "year_from": YEAR_FROM,
    "year_to": YEAR_TO,
    "highlighted": HIGHLIGHTED,
    "name": NAME,
    "description": DESCRIPTION,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
POSITION_SQL = """
    INSERT INTO position (cv_id, cv_partner_section_id, external_unique_id, year_from, year_to, highlighted, name, description, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :year_from, :year_to, :highlighted, :name, :description, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, year_from=EXCLUDED.year_from, year_to=EXCLUDED.year_to, highlighted=EXCLUDED.highlighted, name=EXCLUDED.name, description=EXCLUDED.description, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_positions(conn, df: pd.DataFrame):
    upsert_section(conn, df, POSITION_SQL, POSITION_FIELDS)


BLOG_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "name": NAME,
    "description": DESCRIPTION,
    "highlighted": HIGHLIGHTED,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
BLOG_SQL = """
    INSERT INTO blog_publication (cv_id, cv_partner_section_id, external_unique_id, name, description, highlighted, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :name, :description, :highlighted, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, name=EXCLUDED.name, description=EXCLUDED.description, highlighted=EXCLUDED.highlighted, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_blogs(conn, df: pd.DataFrame):
    upsert_section(conn, df, BLOG_SQL, BLOG_FIELDS)


CV_ROLE_FIELDS = {
    "name": NAME,
    "description": DESCRIPTION,
    "highlighted": HIGHLIGHTED,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
CV_ROLE_SQL = """
    INSERT INTO cv_role (cv_id, name, description, highlighted, updated, updated_by_owner)
    VALUES (:cv_id, :name, :description, :highlighted, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, name) DO UPDATE
    SET description=EXCLUDED.description, highlighted=EXCLUDED.highlighted, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_cv_roles(conn, df: pd.DataFrame):
    upsert_section(conn, df, CV_ROLE_SQL, CV_ROLE_FIELDS)


KEY_QUALIFICATION_FIELDS = {
    "cv_partner_section_id": CV_PARTNER_SECTION_ID,
    "external_unique_id": EXTERNAL_UNIQUE_ID,
    "label": LABEL,
    "summary": SUMMARY_OF_QUALIFICATIONS,
    "short_description": SHORT_DESCRIPTION,
    "updated": UPDATED,
    "updated_by_owner": UPDATED_BY_OWNER,
}
KEY_QUALIFICATION_SQL = """
    INSERT INTO key_qualification (cv_id, cv_partner_section_id, external_unique_id, label, summary, short_description, updated, updated_by_owner)
    VALUES (:cv_id, :cv_partner_section_id, :external_unique_id, :label, :summary, :short_description, :updated, :updated_by_owner)
    ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
    SET external_unique_id=EXCLUDED.external_unique_id, label=EXCLUDED.label, summary=EXCLUDED.summary, short_description=EXCLUDED.short_description, updated=EXCLUDED.updated, updated_by_owner=EXCLUDED.updated_by_owner
"""


def upsert_key_qualifications(conn, df: pd.DataFrame):
    upsert_section(conn, df, KEY_QUALIFICATION_SQL, KEY_QUALIFICATION_FIELDS)


def upsert_sc_clearance(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} security clearances...")
    sql = text(
        """
        INSERT INTO user_clearance(user_id, clearance_id, valid_from, valid_to, verified_by, notes)
        VALUES (:user_id, :clearance_id, :valid_from, :valid_to, :verified_by, :notes)
        ON CONFLICT (user_id, clearance_id, valid_from) DO UPDATE
        SET valid_to    = EXCLUDED.valid_to,
            verified_by = EXCLUDED.verified_by,
            notes       = EXCLUDED.notes
    """
    )
    payload = []
    for _, row in df.iterrows():
        uid = _lookup_user_id(conn, row.get(EMAIL), row.get(UPN), row.get(EXTERNAL_USER_ID))
        if not uid:
            continue

        clearance_name = _normalize_string(row.get(CLEARANCE), DEFAULT_CLEARANCE) or DEFAULT_CLEARANCE
        conn.execute(text("INSERT INTO dim_clearance(name) VALUES (:n) ON CONFLICT(name) DO NOTHING"), {"n": clearance_name})
        clearance_id = conn.execute(
            text("SELECT clearance_id FROM dim_clearance WHERE name=:n"), {"n": clearance_name}
        ).scalar()

        valid_from_date = _parse_date(row.get(VALID_FROM), default=_parse_date(DEFAULT_DATE))
        valid_to_date = _parse_date(row.get(VALID_TO))
        verified_by = _normalize_string(row.get(VERIFIED_BY), None) or None
        notes = _normalize_string(row.get(NOTES), None) or None

        if valid_to_date and valid_from_date and valid_to_date < valid_from_date:
            valid_to_date = None

        payload.append(
            {
                "user_id": uid,
                "clearance_id": clearance_id,
                "valid_from": valid_from_date,
                "valid_to": valid_to_date,
                "verified_by": verified_by,
                "notes": notes,
            },
        )
    if payload:
        conn.execute(sql, payload)


def upsert_availability(conn, df: pd.DataFrame):
    if df is None or df.empty:
        return
    logger.info(f"Upserting {len(df)} availability rows...")
    sql = text(
        """
        INSERT INTO user_availability(user_id, date, percent_available, source)
        VALUES (:user_id, :date, :percent_available, :source)
        ON CONFLICT (user_id, date) DO UPDATE
        SET percent_available = EXCLUDED.percent_available,
            source            = EXCLUDED.source,
            updated_at        = NOW()
    """
    )
    payload = []
    for _, row in df.iterrows():
        uid = _lookup_user_id(conn, row.get(EMAIL), row.get(UPN), row.get(EXTERNAL_USER_ID))
        if not uid:
            continue
        raw_percent = row.get(PERCENT_AVAILABLE)
        percent = 0 if raw_percent is None or (isinstance(raw_percent, float) and pd.isna(raw_percent)) else int(float(raw_percent))
        percent = max(0, min(100, percent))
        payload.append(
            {
                "user_id": uid,
                "date": _normalize_string(row.get(DATE), None) or None,
                "percent_available": percent,
                "source": _normalize_string(row.get(SOURCE), DEFAULT_SOURCE),
            },
        )
    if payload:
        conn.execute(sql, payload)


def load(clean_data, engine: Engine) -> None:
    """
    Run all upserts inside a single transaction.
    """
    with engine.begin() as conn:
        upsert_users(conn, getattr(clean_data, "users_df", None))
        upsert_cvs(conn, getattr(clean_data, "cvs_df", None))
        upsert_technologies(conn, getattr(clean_data, "technologies_df", None))
        upsert_languages(conn, getattr(clean_data, "languages_df", None))
        upsert_project_experiences(conn, getattr(clean_data, "project_experiences_df", None))
        upsert_work_experiences(conn, getattr(clean_data, "work_experiences_df", None))
        upsert_certifications(conn, getattr(clean_data, "certifications_df", None))
        upsert_courses(conn, getattr(clean_data, "courses_df", None))
        upsert_educations(conn, getattr(clean_data, "educations_df", None))
        upsert_positions(conn, getattr(clean_data, "positions_df", None))
        upsert_blogs(conn, getattr(clean_data, "blogs_df", None))
        upsert_cv_roles(conn, getattr(clean_data, "cv_roles_df", None))
        upsert_key_qualifications(conn, getattr(clean_data, "key_qualifications_df", None))
        upsert_sc_clearance(conn, getattr(clean_data, "sc_clearance_df", None))
        upsert_availability(conn, getattr(clean_data, "availability_df", None))
    logger.info("Load complete.")


__all__ = [
    "load",
    "upsert_users",
    "upsert_cvs",
    "upsert_technologies",
    "upsert_languages",
    "upsert_project_experiences",
    "upsert_work_experiences",
    "upsert_certifications",
    "upsert_courses",
    "upsert_educations",
    "upsert_positions",
    "upsert_blogs",
    "upsert_cv_roles",
    "upsert_key_qualifications",
    "upsert_sc_clearance",
    "upsert_availability",
]
