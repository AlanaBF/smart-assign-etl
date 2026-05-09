import pandas as pd
import pytest

from flowcase_etl_pipeline.transform import transform, parse_multilang, to_iso_date


def test_transform_parses_multilang_and_counts():
    users = pd.DataFrame(
        {
            "CV Partner User ID": [1],
            "CV Partner CV ID": ["cv-1"],
            "Name (multilang)": ["int:Jane Doe|no:Jane"],
            "Title (#{lang})": ["int:Engineer"],
            "SFIA Level": [4],
        }
    )
    usage = pd.DataFrame(
        {
            "CV Partner User ID": [1],
            "Nationality (#{lang})": ["int:UK"],
        }
    )

    raw = {"user_report.csv": users, "usage_report.csv": usage}
    result = transform(raw)

    assert len(result.users_df) == len(result.cvs_df) == 1
    assert result.users_df.iloc[0]["Name (multilang)"]["int"] == "Jane Doe"
    assert result.users_df.iloc[0]["nationality_multilang"]["int"] == "UK"
    assert result.cvs_df.iloc[0]["sfia_level"] == 4


def test_transform_normalises_dates():
    raw = {
        "user_report.csv": pd.DataFrame({"CV Partner User ID": [1]}),
        "usage_report.csv": pd.DataFrame({"CV Partner User ID": [1]}),
        "sc_clearance.csv": pd.DataFrame(
            {
                "Email": ["a@example.com"],
                "Valid From": ["01/02/2024"],
                "Valid To": ["2024-12-31"],
            }
        ),
        "availability_report.csv": pd.DataFrame({"Email": ["a@example.com"], "Date": ["2024-03-05"]}),
    }

    result = transform(raw)
    assert result.sc_clearance_df.iloc[0]["Valid From"] == to_iso_date("01/02/2024")
    assert result.availability_df.iloc[0]["Date"] == to_iso_date("2024-03-05")


def test_transform_raises_when_users_missing():
    with pytest.raises(ValueError):
        transform({"user_report.csv": pd.DataFrame(), "usage_report.csv": pd.DataFrame()})


def test_transform_handles_missing_multilang_and_title():
    users = pd.DataFrame(
        {
            "CV Partner User ID": [1],
            "CV Partner CV ID": ["cv-1"],
        }
    )
    raw = {"user_report.csv": users, "usage_report.csv": pd.DataFrame()}
    result = transform(raw)
    assert result.users_df.iloc[0]["Name (multilang)"] == {}
    assert result.cvs_df.iloc[0]["title_multilang"] == {}

def test_transform_defaults_when_multilang_missing():
    users = pd.DataFrame([{"CV Partner User ID": "u1"}])
    usage = pd.DataFrame([{"CV Partner User ID": "u1"}])
    tr = transform({"user_report.csv": users, "usage_report.csv": usage})
    assert tr.users_df["Name (multilang)"].iloc[0] == {}
    assert tr.users_df["nationality_multilang"].iloc[0] == {}
