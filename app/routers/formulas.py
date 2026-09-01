"""Formula reference endpoint (F05 — M-10).

Serves the plain-English `formula_version.description` column (14/14 populated,
guardrail-safe) so the report's lineage drawers render real descriptions instead
of hardcoded copy. Reference data — authenticated, not org-scoped.
"""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role
from app.db import supabase_rest_get

router = APIRouter(prefix="/api/formulas", tags=["formulas"])


@router.get("")
async def list_formula_descriptions(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Return {formula_id → {name, description}} from formula_version."""
    r = await supabase_rest_get(
        "formula_version",
        select="formula_id,name,description",
        limit=200,
    )
    rows = r.json() if r.status_code == 200 else []
    descriptions = {
        row["formula_id"]: {
            "name": row.get("name", ""),
            "description": row.get("description", ""),
        }
        for row in rows
        if isinstance(row, dict) and row.get("formula_id")
    }
    return {"formulas": descriptions}

@router.get("/method-version")
async def method_version():
    """PUBLIC — the version of the published method, and the change policy.

    A published score survives third-party scrutiny partly because the regime
    behind it is versioned and its changes are announced before they take
    effect. `/methodology` is a public page, so this endpoint is public too:
    a reader who did not buy the report must be able to check the method.

    It exposes ONLY the formula-set version and count — never a description, a
    weight, or a threshold. Nothing here is invented: if `formula_version`
    carries no version, the response says so rather than returning a plausible
    number (Hard Rule 7).
    """
    r = await supabase_rest_get(
        "formula_version",
        select="formula_id,version,effective_date",
        limit=200,
    )
    rows = r.json() if r.status_code == 200 else []
    rows = [x for x in rows if isinstance(x, dict) and x.get("formula_id")]

    versions = sorted({str(x["version"]) for x in rows if x.get("version")})
    dates = sorted({str(x["effective_date"]) for x in rows if x.get("effective_date")})

    return {
        "formula_count": len(rows) or None,
        # A set of one is "the" version; several means the formulas are not in
        # lockstep, which is a fact worth showing rather than flattening.
        "versions": versions or None,
        "effective_from": dates[0] if dates else None,
        "last_effective": dates[-1] if dates else None,
    }
