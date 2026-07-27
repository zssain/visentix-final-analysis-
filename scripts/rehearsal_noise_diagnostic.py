"""Labeled diagnostic: apply the decompose-v2 noise filter to the STORED rehearsal
notice and report before/after presence-count dimensions. READ-ONLY — no DB writes;
stored rehearsal rows are untouched (Rule 6 / task Phase B step 5).

Run: PYTHONPATH=. .venv/bin/python scripts/rehearsal_noise_diagnostic.py
"""

from collections import Counter

import httpx

from app.config import settings
from app.services.intake.decompose import _section_structural_noise
from app.services.profiling.live_profile import compute_org_profile

ORG_ID = "066745ed-3a22-48bb-94e4-e3f002787bdb"   # 1-800-Flowers (rehearsal)
NOTICE_ID = "91a04e55-b825-46b9-924b-3ca44ff4fe5b"

URL = settings.supabase_url
H = {"apikey": settings.supabase_service_role_key,
     "Authorization": f"Bearer {settings.supabase_service_role_key}"}


def _get(path):
    return httpx.get(f"{URL}/rest/v1/{path}", headers=H, timeout=30).json()


def _flag_sections(sections):
    """Return {section_id: noise_reason or None} applying the exact decompose-v2 rule."""
    seen, flags = {}, {}
    for s in sorted(sections, key=lambda x: x.get("sequence", 0)):
        text = s.get("extracted_text") or ""
        reason = _section_structural_noise(text)
        key = " ".join(text.strip().lower().split())
        if reason is None and key and key in seen:
            reason = f"duplicate_of:{seen[key]}"
        if key and key not in seen:
            seen[key] = s["section_id"]
        flags[s["section_id"]] = reason
    return flags


def main():
    sections = _get(f"notice_section?select=section_id,sequence,extracted_text&notice_id=eq.{NOTICE_ID}&limit=400")
    sec_flags = _flag_sections(sections)

    clauses = []
    sec_ids = [s["section_id"] for s in sections]
    for i in range(0, len(sec_ids), 40):
        in_list = ",".join(f'"{x}"' for x in sec_ids[i:i + 40])
        clauses += _get(f"disclosure_clause?select=clause_id,section_id,category,clause_type,raw_text"
                        f"&section_id=in.({in_list})&limit=2000")

    def is_noise(c):
        if len((c.get("raw_text") or "").strip()) < 20:
            return True
        return sec_flags.get(c.get("section_id")) is not None

    noise = [c for c in clauses if is_noise(c)]
    clean = [c for c in clauses if not is_noise(c)]

    org = _get(f"organization?select=organization_id,industry,size,geography&organization_id=eq.{ORG_ID}")
    org_row = org[0] if org else {"organization_id": ORG_ID, "industry": "unknown", "size": "unknown", "geography": "US"}

    def prof(rows):
        return compute_org_profile(org_row, [{"category": c.get("category") or "other",
                                              "clause_type": c.get("clause_type") or ""} for c in rows],
                                   profile_version=1)

    p_all, p_clean = prof(clauses), prof(clean)
    reason_counts = Counter((sec_flags.get(c["section_id"]) or "clause_fragment").split(":")[0]
                            for c in noise)

    print(f"sections={len(sections)} clauses={len(clauses)} "
          f"noise={len(noise)} ({len(noise)/max(len(clauses),1)*100:.0f}%) clean={len(clean)}")
    print("noise_reason breakdown:", dict(reason_counts))
    print(f"{'dim':<8}{'ALL':>10}{'CLEAN':>10}{'delta':>10}")
    for name, a, c in [("PGMS", p_all.pgms, p_clean.pgms),
                       ("DSI", p_all.dsi, p_clean.dsi),
                       ("AIGMS", p_all.aigms, p_clean.aigms)]:
        print(f"{name:<8}{a:>10.2f}{c:>10.2f}{c-a:>10.2f}")


if __name__ == "__main__":
    main()
