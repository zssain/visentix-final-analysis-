"""Per-family source connectors built on the ingestion framework."""

from app.services.ingestion.connectors.hhs_ocr import HHSOCRConnector

__all__ = ["HHSOCRConnector"]
