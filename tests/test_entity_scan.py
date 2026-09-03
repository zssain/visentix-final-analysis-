"""F01 deterministic multi-notice data-quality scan."""

from app.services.intake.decompose import decompose
from app.services.intake.entity_scan import scan_notice_entities


def test_normal_notice_does_not_flag():
    notice = decompose(
        """# Acme Retail Group Privacy Notice

This Privacy Notice describes how Acme Retail Group collects and uses personal information.

## Your choices

You may contact us to exercise your privacy choices.
"""
    )
    result = scan_notice_entities(notice)
    assert result.flagged is False
    assert result.detected_entities == ()
    assert result.confidence is None


def test_two_concatenated_notices_flag_both_self_identifying_entities():
    notice = decompose(
        """# Acme Retail Group Privacy Notice

This Privacy Notice describes how Acme Retail Group collects and uses personal information.

## Contact us

Contact Acme Retail Group with questions about this notice.

# Northwind Services Privacy Policy

This Privacy Policy describes how Northwind Services processes and shares personal data.

## Contact us

Contact Northwind Services with questions about this policy.
"""
    )
    result = scan_notice_entities(notice)
    assert result.flagged is True
    assert result.detected_entities == ("Acme Retail Group", "Northwind Services")
    assert result.confidence is None
    assert {e["signal"] for e in result.evidence} >= {
        "entity_privacy_heading", "notice_describes_entity"
    }
    assert all("excerpt" not in e and "text" not in e for e in result.evidence)


def test_passing_partner_mention_does_not_flag():
    notice = decompose(
        """# Acme Retail Group Privacy Notice

This Privacy Notice describes how Acme Retail Group collects personal information.

## Service providers

We may share delivery details with Northwind Services as a service provider.
"""
    )
    result = scan_notice_entities(notice)
    assert result.flagged is False


def test_defined_as_we_signals_are_deterministic():
    notice = decompose(
        """Alpha Holdings (\"we\", \"us\", or \"our\") explains its data practices.

Beta Labs (\"we\", \"us\", or \"our\") explains its data practices.

You may contact the relevant company for details.
"""
    )
    result = scan_notice_entities(notice)
    assert result.flagged is True
    assert result.detected_entities == ("Alpha Holdings", "Beta Labs")
