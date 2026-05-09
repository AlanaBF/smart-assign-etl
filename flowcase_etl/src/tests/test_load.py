import pandas as pd
import pytest

from flowcase_etl_pipeline import load as load_mod
from flowcase_etl_pipeline.transform import TransformResult


def test_helpers():
    assert load_mod._parse_boolean("yes") is True
    assert load_mod._parse_boolean("No") is False
    assert load_mod._normalize_string("  hi ") == "hi"
    assert load_mod._normalize_string(None, default="x") == "x"
    assert load_mod._parse_date("2024-01-02").isoformat() == "2024-01-02"


class FakeResult:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value


class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(params)
        return FakeResult()


class ConnWithMapping:
    """Returns preset scalar values when the SQL string contains a given key."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        for key, value in self.mapping.items():
            if key in str(sql):
                return FakeResult(value)
        return FakeResult()


def test_lookup_user_id_prefers_email_then_upn_then_external():
    conn = ConnWithMapping(
        {
            "lower(email)": 1,
            "lower(upn)": 2,
            "external_user_id": 3,
        }
    )
    assert load_mod._lookup_user_id(conn, email="a@x.com") == 1
    assert load_mod._lookup_user_id(conn, email=None, upn="u") == 2
    assert load_mod._lookup_user_id(conn, email=None, upn=None, external_id="ext") == 3
    assert load_mod._lookup_user_id(conn, email=None, upn=None, external_id=None) is None


def test_ensure_dimension_exists_returns_none_for_blank_and_inserts_when_present():
    conn = ConnWithMapping({"SELECT industry_id": 9})
    assert load_mod._ensure_dimension_exists(conn, "dim_industry", None) is None  
    value = load_mod._ensure_dimension_exists(conn, "dim_industry", "Energy")
    assert value == 9


def test_upsert_users_handles_empty_df():
    conn = FakeConn()
    load_mod.upsert_users(conn, pd.DataFrame())
    assert conn.calls == []


def test_upsert_cvs_inserts_when_user_found():
    mapping = {"SELECT user_id FROM users": 42}
    conn = ConnWithMapping(mapping)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner User ID": ["user-1"],
            "title_multilang": [{"int": "Title"}],
            "Years of education": [10],
            "Years since first work experience": [5],
            "Has profile image": [True],
            "Owns a reference project": [False],
            "Read and understood privacy notice": [True],
            "CV Last updated by owner": ["2024-01-01"],
            "CV Last updated": ["2024-01-02"],
        }
    )
    load_mod.upsert_cvs(conn, df)
    assert len(conn.calls) >= 2


def test_upsert_technologies_skips_unknown_cv_and_inserts_known():
    mapping = {"SELECT technology_id": 7, "SELECT cv_id FROM cvs": None}

    class ConnToggle(ConnWithMapping):
        def execute(self, sql, params=None):
            if params and "cv-present" in str(params):
                self.mapping["SELECT cv_id FROM cvs"] = 5
            return super().execute(sql, params)

    conn = ConnToggle(mapping)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-missing", "cv-present"],
            "Skill name": ["Python", "SQL"],
            "Year experience": [3, 2],
            "Proficiency (0-5)": [4, 3],
            "Is official masterdata (in #{lang})": [{"int": "Yes"}, {"int": "Yes"}],
        }
    )
    load_mod.upsert_technologies(conn, df)
    assert any("cv_technology" in call[0] for call in conn.calls if isinstance(call, tuple))


def test_upsert_courses_skips_when_cv_missing(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: None)
    conn = FakeConn()
    df = pd.DataFrame({"CV Partner CV ID": ["cv-1"]})
    load_mod.upsert_courses(conn, df)
    assert conn.calls == []


def test_upsert_sc_clearance_handles_empty_and_missing_user(monkeypatch):
    conn = FakeConn()
    load_mod.upsert_sc_clearance(conn, pd.DataFrame())
    assert conn.calls == []

    monkeypatch.setattr(load_mod, "_lookup_user_id", lambda conn, email, upn, external_id: None)
    df = pd.DataFrame({"Email": ["a@example.com"], "Clearance": ["SC"]})
    load_mod.upsert_sc_clearance(conn, df)
    assert conn.calls == []


def test_upsert_availability_handles_empty_and_missing_user(monkeypatch):
    conn = FakeConn()
    load_mod.upsert_availability(conn, pd.DataFrame())
    assert conn.calls == []

    monkeypatch.setattr(load_mod, "_lookup_user_id", lambda conn, email, upn, external_id: None)
    df = pd.DataFrame({"Email": ["a@example.com"], "Date": ["2024-01-01"], "Percent Available": [50]})
    load_mod.upsert_availability(conn, df)
    assert conn.calls == []


def test_upsert_section_inserts_when_get_cv_id_present(monkeypatch):
    def fake_get_cv_id(conn, cv_partner_cv_id):
        return 123 if cv_partner_cv_id != "skip" else None

    monkeypatch.setattr(load_mod, "_get_cv_id", fake_get_cv_id)

    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["keep", "skip"],
            "CV Partner section ID": ["s1", "s2"],
            "External unique ID": ["e1", "e2"],
        }
    )
    fields = {
        "cv_partner_section_id": "CV Partner section ID",
        "external_unique_id": "External unique ID",
    }
    sql = """
        INSERT INTO work_experience (cv_id, cv_partner_section_id, external_unique_id)
        VALUES (:cv_id, :cv_partner_section_id, :external_unique_id)
        ON CONFLICT (cv_id, cv_partner_section_id) DO UPDATE
        SET external_unique_id=EXCLUDED.external_unique_id
    """

    conn = FakeConn()
    load_mod.upsert_section(conn, df, sql, fields)

    assert len(conn.calls) == 1
    params = conn.calls[0][0]
    assert params["cv_id"] == 123
    assert params["cv_partner_section_id"] == "s1"


def test_upsert_users_executes_rows():
    df = pd.DataFrame(
        {
            "CV Partner User ID": [1, 2],
            "Name (multilang)": [{"int": "A"}, {"int": "B"}],
            "Email": ["a@example.com", "b@example.com"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_users(conn, df)
    assert len(conn.calls) == 1
    batch = conn.calls[0]
    assert len(batch) == 2  
    assert batch[0]["cv_partner_user_id"] == "1"
    assert batch[1]["cv_partner_user_id"] == "2"


def test_upsert_courses_json_field(monkeypatch):
    def fake_get_cv_id(conn, cv_partner_cv_id):
        return 999

    monkeypatch.setattr(load_mod, "_get_cv_id", fake_get_cv_id)

    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["s1"],
            "External unique ID": ["ext1"],
            "Month": [1],
            "Year": [2024],
            "Name": ["Course"],
            "Organiser": ["Org"],
            "Long description": ["Desc"],
            "Highlighted": [True],
            "Is official masterdata (in #{lang})": [{"int": "Yes"}],
            "Attachments": ["file.pdf"],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_courses(conn, df)
    assert len(conn.calls) == 1
    payload_list = conn.calls[0]
    assert isinstance(payload_list, list)
    payload = payload_list[0]
    assert payload["cv_id"] == 999
    assert payload["is_official_masterdata"] == '{"int": "Yes"}'


def test_upsert_languages_inserts(monkeypatch):
    def fake_get_cv_id(conn, cv_partner_cv_id):
        return 7

    monkeypatch.setattr(load_mod, "_get_cv_id", fake_get_cv_id)
    monkeypatch.setattr(load_mod, "_ensure_dimension_exists", lambda conn, table, name: 11)

    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "Language": ["English"],
            "Highlighted": [True],
            "Is official masterdata (in #{lang})": [{"int": "Yes"}],
        }
    )
    conn = FakeConn()
    load_mod.upsert_languages(conn, df)
    assert len(conn.calls) == 1
    batch = conn.calls[0]
    assert len(batch) == 1
    payload = batch[0] 
    assert payload["cv_id"] == 7
    assert payload["lang_id"] == 11


def test_upsert_project_experiences(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 3)
    monkeypatch.setattr(load_mod, "_ensure_dimension_exists", lambda conn, table, name: 5)

    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["sec1"],
            "External unique ID": ["ext"],
            "Percent allocated": [50],
            "Project extent (individual hours)": [10],
            "Project extent (hours)": [100],
            "Project extent total (hours)": [200],
            "Project extent": ["hrs"],
            "Project extent (currency)": ["USD"],
            "Project extent total": [1000],
            "Project extent total (currency)": ["USD"],
            "Project area": [1],
            "Project area (unit)": ["unit"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_project_experiences(conn, df)
    assert len(conn.calls) == 1


def test_upsert_work_experiences(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 2)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["w1"],
            "External unique ID": ["ext"],
            "Month from": [1],
            "Year from": [2020],
            "Month to": [2],
            "Year to": [2021],
            "Highlighted": [True],
            "Employer": ["Emp"],
            "Description": ["Desc"],
            "Long Description": [None],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_work_experiences(conn, df)
    assert len(conn.calls) == 1


def test_upsert_certifications(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 5)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["c1"],
            "External unique ID": ["ext"],
            "Month": [1],
            "Year": [2020],
            "Month expire": [None],
            "Year expire": [None],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_certifications(conn, df)
    assert len(conn.calls) == 1


def test_upsert_educations(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 8)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["e1"],
            "External unique ID": ["ext"],
            "Month from": [1],
            "Year from": [2000],
            "Month to": [2],
            "Year to": [2004],
            "Highlighted": [False],
            "Attachments": [None],
            "Place of study": ["Uni"],
            "Degree": ["CS"],
            "Description": ["Desc"],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_educations(conn, df)
    assert len(conn.calls) == 1


def test_upsert_positions(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 9)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["p1"],
            "External unique ID": ["ext"],
            "Year from": [2020],
            "Year to": [2021],
            "Highlighted": [True],
            "Name": ["Role"],
            "Description": ["Desc"],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_positions(conn, df)
    assert len(conn.calls) == 1


def test_upsert_blogs(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 10)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["b1"],
            "External unique ID": ["ext"],
            "Name": ["Post"],
            "Description": ["Desc"],
            "Highlighted": [False],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_blogs(conn, df)
    assert len(conn.calls) == 1


def test_upsert_cv_roles(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 11)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "Name": ["Engineer"],
            "Description": ["Desc"],
            "Highlighted": [True],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_cv_roles(conn, df)
    assert len(conn.calls) == 1


def test_upsert_key_qualifications(monkeypatch):
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 12)
    df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["k1"],
            "External unique ID": ["ext"],
            "Label": ["Lead"],
            "Summary of Qualifications": ["Summary"],
            "Short description": ["Short"],
            "Updated": ["2024-01-01"],
            "Updated by owner": ["2024-01-02"],
        }
    )
    conn = FakeConn()
    load_mod.upsert_key_qualifications(conn, df)
    assert len(conn.calls) == 1


def test_load_orchestrator_runs_all(monkeypatch):
    # Patch helper lookups to fixed IDs
    monkeypatch.setattr(load_mod, "_get_cv_id", lambda conn, cid: 1)
    monkeypatch.setattr(load_mod, "_ensure_dimension_exists", lambda conn, table, name: 1)
    monkeypatch.setattr(load_mod, "_lookup_user_id", lambda conn, email, upn, external_id: 1)

    # Minimal data for each table
    users_df = pd.DataFrame(
        {
            "CV Partner User ID": [1],
            "CV Partner CV ID": ["cv-1"],
            "Name (multilang)": [{"int": "Name"}],
            "nationality_multilang": [{"int": "UK"}],
            "Years of education": [10],
            "Years since first work experience": [5],
            "Has profile image": [True],
            "Owns a reference project": [False],
            "Read and understood privacy notice": [True],
        }
    )
    tech_df = pd.DataFrame(
        {"CV Partner CV ID": ["cv-1"], "Skill name": ["Python"], "Year experience": [5], "Proficiency (0-5)": [4], "Is official masterdata (in #{lang})": [{"int": "Yes"}]}
    )
    lang_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "Language": ["English"], "Highlighted": [True], "Is official masterdata (in #{lang})": [{"int": "Yes"}]})
    proj_df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["p1"],
            "External unique ID": ["ext"],
            "Percent allocated": [50],
            "Project extent (individual hours)": [10],
            "Project extent (hours)": [100],
            "Project extent total (hours)": [200],
            "Project extent": ["hrs"],
            "Project extent (currency)": ["USD"],
            "Project extent total": [1000],
            "Project extent total (currency)": ["USD"],
            "Project area": [1],
            "Project area (unit)": ["unit"],
        }
    )
    work_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["w1"], "External unique ID": ["ext"]})
    cert_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["c1"], "External unique ID": ["ext"]})
    course_df = pd.DataFrame(
        {
            "CV Partner CV ID": ["cv-1"],
            "CV Partner section ID": ["co1"],
            "External unique ID": ["ext"],
            "Name": ["Course"],
            "Organiser": ["Org"],
            "Is official masterdata (in #{lang})": [{"int": "Yes"}],
        }
    )
    edu_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["e1"], "External unique ID": ["ext"]})
    pos_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["p1"], "External unique ID": ["ext"]})
    blog_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["b1"], "External unique ID": ["ext"]})
    cv_role_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "Name": ["Role"]})
    kq_df = pd.DataFrame({"CV Partner CV ID": ["cv-1"], "CV Partner section ID": ["k1"], "External unique ID": ["ext"]})
    sc_df = pd.DataFrame({"Email": ["a@example.com"], "Clearance": ["SC"], "Valid From": ["2024-01-01"], "Valid To": [None], "Verified By": [None], "Notes": [None], "UPN": [None], "External User ID": [None]})
    avail_df = pd.DataFrame({"Email": ["a@example.com"], "Date": ["2024-01-01"], "Percent Available": [50], "Source": ["Manual"], "UPN": [None], "External User ID": [None]})

    clean = TransformResult(
        users_df=users_df,
        cvs_df=users_df.copy(),
        technologies_df=tech_df,
        languages_df=lang_df,
        project_experiences_df=proj_df,
        work_experiences_df=work_df,
        certifications_df=cert_df,
        courses_df=course_df,
        educations_df=edu_df,
        positions_df=pos_df,
        blogs_df=blog_df,
        cv_roles_df=cv_role_df,
        key_qualifications_df=kq_df,
        sc_clearance_df=sc_df,
        availability_df=avail_df,
    )

    class FakeEngine:
        def begin(self):
            return self

        def __enter__(self):
            return FakeConn()

        def __exit__(self, exc_type, exc, tb):
            return False

    load_mod.load(clean, FakeEngine())


def test_upsert_sc_clearance(monkeypatch):
    calls = []

    class Conn:
        def execute(self, sql, params=None):
            calls.append((str(sql), params))
            if "SELECT clearance_id" in str(sql):
                return FakeResult(42)
            return FakeResult()

    monkeypatch.setattr(load_mod, "_lookup_user_id", lambda conn, email, upn, external_id: 10)

    df = pd.DataFrame(
        {
            "Email": ["a@example.com"],
            "Clearance": ["SC"],
            "Valid From": ["2024-01-02"],
            "Valid To": ["2023-01-01"],  
            "Verified By": ["HR"],
            "Notes": ["note"],
        }
    )
    conn = Conn()
    load_mod.upsert_sc_clearance(conn, df)
    assert any("dim_clearance" in sql for sql, _ in calls)
    assert any("user_clearance" in sql for sql, _ in calls)


def test_upsert_availability_clamps(monkeypatch):
    monkeypatch.setattr(load_mod, "_lookup_user_id", lambda conn, email, upn, external_id: 5)
    df = pd.DataFrame(
        {
            "Email": ["a@example.com", "b@example.com"],
            "Percent Available": [150, None],
            "Date": ["2024-01-01", "2024-01-02"],
            "Source": ["Manual", None],
        }
    )
    conn = FakeConn()
    load_mod.upsert_availability(conn, df)
    assert len(conn.calls) == 1
    batch = conn.calls[0]
    assert len(batch) == 2  
    assert batch[0]["percent_available"] == 100  
    assert batch[1]["percent_available"] == 0    
    assert batch[1]["source"] == "Fake generator" 
