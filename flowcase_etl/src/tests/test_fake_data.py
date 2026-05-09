"""Tests for flowcase_etl_pipeline.fake_data module."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from flowcase_etl_pipeline import fake_data


class TestFakeDataMain:
    @patch("flowcase_etl_pipeline.fake_data.subprocess.run")
    def test_main_calls_script(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        fake_data.main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # First positional arg is a list with python executable and script path
        args_list = call_args[0][0]
        assert args_list[0] == sys.executable
        assert "make_fake_flowcase_reports.py" in args_list[1]
        # check=True should be passed
        assert call_args[1]["check"] is True

    @patch("flowcase_etl_pipeline.fake_data.subprocess.run")
    def test_main_raises_on_failure(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        with pytest.raises(subprocess.CalledProcessError):
            fake_data.main()
