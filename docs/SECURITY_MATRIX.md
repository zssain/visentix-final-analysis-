# Security Matrix — Visentix MVP

## Route Access Control

| Route | Method | customer | sme | admin | Public |
|---|---|---|---|---|---|
| `/health` | GET | - | - | - | Yes |
| `/assessments/` | GET | Yes | Yes | Yes | - |


| `/findings/` | GET | Yes | Yes | Yes | - |
| `/reports/{id}` | GET | Yes* | Yes | Yes | - |
| `/reports/{id}/pdf` | GET | Yes* | Yes | Yes | - |
| `/review/queue` | GET | - | Yes | Yes | - |
| `/review/{id}` | GET | - | Yes | Yes | - |
| `/review/finding/{id}/{fid}` | POST | - | Yes | Yes | - |
| `/review/{id}/approve` | POST | - | Yes | Yes | - |
| `/review/gate-mode` | GET/POST | - | - | Yes | - |
| `/admin/status` | GET | - | - | Yes | - |
| `/admin/trigger-assessment` | POST | - | - | Yes | - |
| `/admin/training-stats` | GET | - | - | Yes | - |

*Customer report access governed by `gate_mode`: strict=blocked until approved,
instant_draft=visible with DRAFT banner, client_reviews=visible with banner.

## Row-Level Security (RLS)

| Table | RLS Enabled | Customer Policy | SME/Admin Policy | Service Key |
|---|---|---|---|---|
| profiles | Yes | Own row only | All rows | Bypass |
| risk_finding | Yes | Own org only | All rows | Bypass |
| report_snapshot | Yes | Own org only | All rows | Bypass |
| derived_data_item | Yes | Own org only | All rows | Bypass |
| organization_intelligence_profile | Yes | Own org only | All rows | Bypass |
| organization | No (public ref) | All (read) | All | Bypass |
| disclosure_clause | No (corpus) | All (read) | All | Bypass |
| finding_type | No (catalog) | All (read) | All | Bypass |
| recommendation_library | No (catalog) | All (read) | All | Bypass |
| exemplar | No (no route exposes) | Not routed | Not routed | Bypass |
| training_label | No (admin-only route) | Not routed | Not routed | Bypass |

## Key Security Properties

1. **Service-role key**: Server-side only (`app/db.py`). Never in frontend, never
   in logs, never in any response.
2. **Anon key + RLS**: Browser uses anon key. RLS policies enforce org-level
   isolation via `profiles.organization_id = auth.uid()`.
3. **JWT verification**: HS256 signature + expiry + audience checked on every
   authenticated request.
4. **SSRF defense**: URL intake validates DNS resolution against blocked ranges
   (private/loopback/link-local/metadata) before connecting.
5. **Guardrail**: All generated prose passes through `enforce()`. Banned terms
   hard-fail report generation.
6. **VCI suppression**: Scores with VCI < 40 flagged do-not-present.
7. **No fabricated numbers**: Narrative verifier blocks LLM from introducing numbers
   not in the source statement.
8. **Exemplar gate**: Only `sme_cleaned=true` exemplars reach customer reports.
9. **Snapshot reproducibility**: Reports regenerate identically from stored data.
