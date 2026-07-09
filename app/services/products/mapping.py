"""Product mapping — VICBNF-006.

Maps intelligence objects to Visentix products (One-Time, GRC, White-Label,
Quarterly). Every object shown MUST carry its VCI.

Config loaded from config/product_mapping.json — single source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "product_mapping.json"

with open(_CONFIG_PATH) as _f:
    _CFG = json.load(_f)

PRODUCTS = _CFG["products"]
VCI_REVIEW_THRESHOLDS = _CFG["vci_review_thresholds"]

# Threshold below which objects are routed for analyst review
VCI_ROUTE_FOR_REVIEW = VCI_REVIEW_THRESHOLDS["route_for_review"]      # 60
VCI_DO_NOT_PRESENT = VCI_REVIEW_THRESHOLDS["do_not_present_as_definitive"]  # 40


def objects_for_product(product_type: str) -> list[dict]:
    """Return the list of intelligence objects + visibility notes for a product.

    Each entry: {object_type, visibility}.
    Raises KeyError if product_type is unknown.
    """
    product = PRODUCTS.get(product_type)
    if not product:
        raise KeyError(f"Unknown product type: {product_type}. Valid: {list(PRODUCTS.keys())}")
    return product["objects"]


def product_includes(product_type: str) -> dict:
    """Return what a product includes beyond objects."""
    product = PRODUCTS.get(product_type, {})
    return {
        "findings": product.get("includes_findings", False),
        "recommendations": product.get("includes_recommendations", False),
        "methodology": product.get("includes_methodology", False),
        "vci": product.get("includes_vci", True),
        "cohort_disclosure": product.get("includes_cohort_disclosure", True),
    }


def is_object_in_product(object_type: str, product_type: str) -> bool:
    """Check if an object_type is included in a product."""
    try:
        objects = objects_for_product(product_type)
        return any(o["object_type"] == object_type for o in objects)
    except KeyError:
        return False


def visibility_note(object_type: str, product_type: str) -> str:
    """Get the visibility note for an object in a product."""
    try:
        objects = objects_for_product(product_type)
        for o in objects:
            if o["object_type"] == object_type:
                return o["visibility"]
    except KeyError:
        pass
    return ""


def needs_analyst_review(vci_score: float) -> bool:
    """Check if a VCI score requires analyst review (spec: <60 = Low/Very Low)."""
    return vci_score < VCI_ROUTE_FOR_REVIEW


def should_not_present_as_definitive(vci_score: float) -> bool:
    """Check if VCI is too low to present as definitive (spec: <40 = Very Low)."""
    return vci_score < VCI_DO_NOT_PRESENT
