"""Config endpoints — serve the engine's real vocabularies to the frontend so
intake options can't drift from what scoring understands (ARCH-001A)."""

from fastapi import APIRouter

from app.auth import AuthenticatedUser, require_role
from app.services.intake_options import intake_options

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/intake-options")
async def get_intake_options(
    user: AuthenticatedUser = require_role("customer", "sme", "admin"),
):
    """Industry + state-privacy-law options for the intake filters, sourced from
    `config/org_profile_weights.json` (the same config scoring reads)."""
    return intake_options()
