# flowcase_etl_pipeline/flowcase_client.py

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import time
import requests
from .config import FlowcaseConfig

REPORT_TYPES: list[str] = [
    "user_report",
    "usage_report",
    "project_experiences",
    "certifications",
    "courses",
    "languages",
    "technologies",
    "key_qualifications",
    "educations",
    "work_experiences",
    "positions",
    "blogs",
    "cv_roles",
]


@dataclass
class FlowcaseClient:
    cfg: FlowcaseConfig

    @property
    def base_url(self) -> str:
        return f"https://{self.cfg.subdomain}.flowcase.com"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.api_token}",
            "Accept": "application/json",
        }

    def fetch_office_ids(self) -> list[str]:
        """
        Fetch office IDs from /api/v1/countries.
        If FlowcaseConfig.office_ids is set, we just return that.
        """
        if self.cfg.office_ids:
            return self.cfg.office_ids

        url = f"{self.base_url}/api/v1/countries"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        countries = r.json()

        office_ids: list[str] = []
        for country in countries:
            for office in country.get("offices", []):
                office_id = office.get("_id")
                if office_id:
                    office_ids.append(office_id)
        return office_ids

    def initiate_report(
        self,
        report_type: str,
        office_ids: Iterable[str],
        must: list[dict] | None = None,
    ) -> dict:
        """
        POST /api/v2/cv-report?encoding=UTF-8&output_format=csv&report_type=...
        """
        params: dict[str, object] = {
            "encoding": "UTF-8",
            "output_format": "csv",
            "report_type": report_type,
        }

        if self.cfg.lang_params:
            for lang in self.cfg.lang_params:
                params.setdefault("lang[]", []).append(lang)

        payload = {
            "office_ids": list(office_ids),
            "must": must or [],
        }
        url = f"{self.base_url}/api/v2/cv-report"
        r = requests.post(url, params=params, json=payload,
                          headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def poll_report(self, report_id: str, *, poll_interval: int = 5,
                    timeout_seconds: int = 600) -> dict:
        """
        GET /api/v2/cv-report/<report_id> until state == 'finished'
        or timeout.
        """
        url = f"{self.base_url}/api/v2/cv-report/{report_id}"
        deadline = time.time() + timeout_seconds

        while True:
            r = requests.get(url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            data = r.json()

            state = data.get("state")
            if state == "finished":
                return data

            if time.time() >= deadline:
                raise TimeoutError(
                    f"Report {report_id} did not finish within "
                    f"{timeout_seconds} seconds (state={state!r})"
                )

            time.sleep(poll_interval)

    def download_report_file(self, report_meta: dict, dest_path: Path) -> None:
        """
        When finished, report_meta["cv_report"]["url"] is a signed URL.
        Download and save as CSV.
        """
        url = (
            (report_meta.get("cv_report") or {}).get("url")
            or None
        )
        if not url:
            raise RuntimeError("Report meta has no download URL yet")

        r = requests.get(url, timeout=60)
        r.raise_for_status()

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(r.content)

    def fetch_all_reports(
        self,
        output_dir: Path,
        report_types: Iterable[str] = REPORT_TYPES,
        must: list[dict] | None = None,
    ) -> None:
        """
        For each report type, initiate, poll, and download CSV
        with the standard filenames (user_report.csv, etc.).
        """
        output_dir.mkdir(parents=True, exist_ok=True) 
        
        office_ids = self.fetch_office_ids()

        for report_type in report_types:
            init_meta = self.initiate_report(
                report_type=report_type,
                office_ids=office_ids,
                must=must,
            )
            report_id = init_meta["_id"]

            final_meta = self.poll_report(report_id)

            dest = output_dir / f"{report_type}.csv"
            self.download_report_file(final_meta, dest)
