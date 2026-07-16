# logs/ — Our Traces

Three human-curated logs plus machine exports. The weekly audit agent reads all of it. Full discipline: see `logging-and-audit.md` at the repo root of this bundle.

| Path | What goes here | Who writes |
|---|---|---|
| `decision-log.md` | One line per judgment call not captured in a spec changelog. Append-only, newest first. | Anyone, the moment the decision is made |
| `incidents/YYYY-MM-DD-slug.md` | One file per incident (anything that cost >1h or touched a hard rule). Use `incidents/_TEMPLATE.md`. Blameless. | Whoever was closest to it, same day |
| `audits/YYYY-MM-DD-audit.md` | Weekly audit reports. | The audit agent (via PR) |
| `exports/` | Optional machine dumps for the auditor: weekly grep of production ERROR lines, pipeline failure summaries, etc. Anything dropped here gets read. | Cron jobs / engineers |

House rules: never edit or delete past entries (append corrections instead) · no names in incident causes · no secrets or customer data anywhere in this folder — reference IDs, not contents.
