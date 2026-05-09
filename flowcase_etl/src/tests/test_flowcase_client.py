"""Tests for flowcase_etl_pipeline.flowcase_client module."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import time

import pytest

from flowcase_etl_pipeline.config import FlowcaseConfig
from flowcase_etl_pipeline.flowcase_client import FlowcaseClient, REPORT_TYPES


@pytest.fixture
def flowcase_config():
    return FlowcaseConfig(
        subdomain="testcompany",
        api_token="test-api-token-123",
        office_ids=None,
        lang_params=None,
    )


@pytest.fixture
def flowcase_config_with_offices():
    return FlowcaseConfig(
        subdomain="testcompany",
        api_token="test-api-token-123",
        office_ids=["office1", "office2"],
        lang_params=["en", "no"],
    )


@pytest.fixture
def client(flowcase_config):
    return FlowcaseClient(cfg=flowcase_config)


@pytest.fixture
def client_with_offices(flowcase_config_with_offices):
    return FlowcaseClient(cfg=flowcase_config_with_offices)


class TestFlowcaseClientInit:
    def test_initialisation(self, client, flowcase_config):
        assert client.cfg == flowcase_config

    def test_base_url(self, client):
        assert client.base_url == "https://testcompany.flowcase.com"


class TestHeaders:
    def test_returns_correct_authorization(self, client):
        headers = client._headers()
        assert headers["Authorization"] == "Bearer test-api-token-123"
        assert headers["Accept"] == "application/json"


class TestFetchOfficeIds:
    def test_returns_config_office_ids_when_set(self, client_with_offices):
        # Should not make any API call
        result = client_with_offices.fetch_office_ids()
        assert result == ["office1", "office2"]

    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_fetches_from_api_when_not_set(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "name": "Country1",
                "offices": [
                    {"_id": "off1", "name": "Office 1"},
                    {"_id": "off2", "name": "Office 2"},
                ],
            },
            {
                "name": "Country2",
                "offices": [
                    {"_id": "off3", "name": "Office 3"},
                ],
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.fetch_office_ids()

        assert result == ["off1", "off2", "off3"]
        mock_get.assert_called_once_with(
            "https://testcompany.flowcase.com/api/v1/countries",
            headers=client._headers(),
            timeout=30,
        )

    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_handles_offices_without_id(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "name": "Country1",
                "offices": [
                    {"_id": "off1", "name": "Office 1"},
                    {"name": "Office without ID"},
                ],
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.fetch_office_ids()

        assert result == ["off1"]


class TestInitiateReport:
    @patch("flowcase_etl_pipeline.flowcase_client.requests.post")
    def test_sends_correct_request(self, mock_post, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"_id": "report123", "state": "pending"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = client.initiate_report(
            report_type="user_report",
            office_ids=["off1", "off2"],
        )

        assert result == {"_id": "report123", "state": "pending"}
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"] == {
            "office_ids": ["off1", "off2"],
            "must": [],
        }
        assert call_kwargs.kwargs["params"]["report_type"] == "user_report"
        assert call_kwargs.kwargs["params"]["encoding"] == "UTF-8"
        assert call_kwargs.kwargs["params"]["output_format"] == "csv"

    @patch("flowcase_etl_pipeline.flowcase_client.requests.post")
    def test_includes_lang_params(self, mock_post, client_with_offices):
        mock_response = MagicMock()
        mock_response.json.return_value = {"_id": "report123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        client_with_offices.initiate_report(
            report_type="user_report",
            office_ids=["off1"],
        )

        call_kwargs = mock_post.call_args
        params = call_kwargs.kwargs["params"]
        assert params["lang[]"] == ["en", "no"]


class TestPollReport:
    @patch("flowcase_etl_pipeline.flowcase_client.time.sleep")
    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_returns_when_finished(self, mock_get, mock_sleep, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "state": "finished",
            "cv_report": {"url": "https://download.example.com/report.csv"},
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.poll_report("report123")

        assert result["state"] == "finished"
        mock_sleep.assert_not_called()

    @patch("flowcase_etl_pipeline.flowcase_client.time.sleep")
    @patch("flowcase_etl_pipeline.flowcase_client.time.time")
    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_polls_until_complete(self, mock_get, mock_time, mock_sleep, client):
        # Simulate: first call pending, second call finished
        mock_response_pending = MagicMock()
        mock_response_pending.json.return_value = {"state": "processing"}
        mock_response_pending.raise_for_status = MagicMock()

        mock_response_finished = MagicMock()
        mock_response_finished.json.return_value = {
            "state": "finished",
            "cv_report": {"url": "https://download.example.com/report.csv"},
        }
        mock_response_finished.raise_for_status = MagicMock()

        mock_get.side_effect = [mock_response_pending, mock_response_finished]
        # time.time() calls: first for deadline, then for check (not expired)
        mock_time.side_effect = [0, 5, 10]

        result = client.poll_report("report123", poll_interval=1, timeout_seconds=600)

        assert result["state"] == "finished"
        mock_sleep.assert_called_once_with(1)

    @patch("flowcase_etl_pipeline.flowcase_client.time.sleep")
    @patch("flowcase_etl_pipeline.flowcase_client.time.time")
    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_raises_timeout(self, mock_get, mock_time, mock_sleep, client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"state": "processing"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # time.time() returns: first call sets deadline=10, then immediately expired
        mock_time.side_effect = [0, 11]

        with pytest.raises(TimeoutError, match="did not finish"):
            client.poll_report("report123", timeout_seconds=10)


class TestDownloadReportFile:
    @patch("flowcase_etl_pipeline.flowcase_client.requests.get")
    def test_downloads_and_saves_file(self, mock_get, client, tmp_path):
        mock_response = MagicMock()
        mock_response.content = b"col1,col2\nval1,val2\n"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        dest = tmp_path / "subdir" / "report.csv"

        report_meta = {"cv_report": {"url": "https://signed-url.example.com/report.csv"}}
        client.download_report_file(report_meta, dest)

        assert dest.exists()
        assert dest.read_bytes() == b"col1,col2\nval1,val2\n"
        mock_get.assert_called_once_with("https://signed-url.example.com/report.csv", timeout=60)

    def test_raises_when_no_url(self, client, tmp_path):
        dest = tmp_path / "report.csv"
        report_meta = {"cv_report": {}}

        with pytest.raises(RuntimeError, match="no download URL"):
            client.download_report_file(report_meta, dest)

    def test_raises_when_cv_report_missing(self, client, tmp_path):
        dest = tmp_path / "report.csv"
        report_meta = {}

        with pytest.raises(RuntimeError, match="no download URL"):
            client.download_report_file(report_meta, dest)


class TestFetchAllReports:
    @patch.object(FlowcaseClient, "download_report_file")
    @patch.object(FlowcaseClient, "poll_report")
    @patch.object(FlowcaseClient, "initiate_report")
    @patch.object(FlowcaseClient, "fetch_office_ids")
    def test_fetches_all_report_types(
        self,
        mock_fetch_offices,
        mock_initiate,
        mock_poll,
        mock_download,
        client,
        tmp_path,
    ):
        mock_fetch_offices.return_value = ["off1", "off2"]
        mock_initiate.return_value = {"_id": "report_id_123"}
        mock_poll.return_value = {
            "state": "finished",
            "cv_report": {"url": "https://example.com/dl.csv"},
        }

        # Only test with a subset for speed
        report_types = ["user_report", "technologies"]
        client.fetch_all_reports(output_dir=tmp_path, report_types=report_types)

        assert mock_fetch_offices.call_count == 1
        assert mock_initiate.call_count == 2
        assert mock_poll.call_count == 2
        assert mock_download.call_count == 2

        # Verify initiate was called with the right report types
        initiate_calls = mock_initiate.call_args_list
        assert initiate_calls[0].kwargs["report_type"] == "user_report"
        assert initiate_calls[1].kwargs["report_type"] == "technologies"

    @patch.object(FlowcaseClient, "download_report_file")
    @patch.object(FlowcaseClient, "poll_report")
    @patch.object(FlowcaseClient, "initiate_report")
    @patch.object(FlowcaseClient, "fetch_office_ids")
    def test_creates_output_dir(
        self,
        mock_fetch_offices,
        mock_initiate,
        mock_poll,
        mock_download,
        client,
        tmp_path,
    ):
        mock_fetch_offices.return_value = ["off1"]
        mock_initiate.return_value = {"_id": "r1"}
        mock_poll.return_value = {"state": "finished", "cv_report": {"url": "http://x"}}

        output_dir = tmp_path / "new_dir" / "nested"
        client.fetch_all_reports(output_dir=output_dir, report_types=["user_report"])

        assert output_dir.exists()

    @patch.object(FlowcaseClient, "download_report_file")
    @patch.object(FlowcaseClient, "poll_report")
    @patch.object(FlowcaseClient, "initiate_report")
    @patch.object(FlowcaseClient, "fetch_office_ids")
    def test_uses_default_report_types(
        self,
        mock_fetch_offices,
        mock_initiate,
        mock_poll,
        mock_download,
        client,
        tmp_path,
    ):
        mock_fetch_offices.return_value = ["off1"]
        mock_initiate.return_value = {"_id": "r1"}
        mock_poll.return_value = {"state": "finished", "cv_report": {"url": "http://x"}}

        client.fetch_all_reports(output_dir=tmp_path)

        assert mock_initiate.call_count == len(REPORT_TYPES)
