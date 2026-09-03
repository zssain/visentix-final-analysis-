"""Report builds fail closed when stored finding codes are not authored."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.routers.reports import _validate_finding_catalog_codes


def test_empty_findings_do_not_query_catalog():
    with patch("app.routers.reports._sb_get") as get:
        _validate_finding_catalog_codes([])
    get.assert_not_called()


def test_known_finding_codes_pass():
    findings = [{"finding_type_code": "AI-004"}, {"finding_type_code": "SH-002"}]
    with patch(
        "app.routers.reports._sb_get",
        return_value=[{"code": "AI-004"}, {"code": "SH-002"}],
    ):
        _validate_finding_catalog_codes(findings)


def test_unknown_finding_code_stops_report_build_without_exposing_code():
    with patch("app.routers.reports._sb_get", return_value=[]):
        with pytest.raises(HTTPException) as exc:
            _validate_finding_catalog_codes([{"finding_type_code": "UNKNOWN-999"}])
    assert exc.value.status_code == 500
    assert "UNKNOWN-999" not in str(exc.value.detail)
