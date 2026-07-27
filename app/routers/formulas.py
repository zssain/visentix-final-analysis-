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
