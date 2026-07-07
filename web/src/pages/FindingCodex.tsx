/**
 * Finding Codex — browsable glossary of all finding codes
 *
 * [MOCK M-11] Codex entries are a static JSON array.
 * Real source: finding_type catalog table in Supabase + /api/codex GET endpoint
 */
import { useState, useMemo } from "react";
import { PageHeader } from "../components/PageHeader";
import "../components/furniture.css";

const DOMAINS = [
  "data_sharing", "tracking_cookies", "consumer_rights",
  "cross_border", "sensitive_data", "retention",
  "children_teens", "ai_automated_decisions", "other",
] as const;
type Domain = typeof DOMAINS[number];

interface CodexEntry {
  code: string;
  domain: Domain;
  title: string;
  definition: string;
  exposure: string;
  example: string;
  related: string[];
}

// [MOCK M-11] — replace with /api/codex endpoint response
const CODEX: CodexEntry[] = [
  { code: "SH-001", domain: "data_sharing",        title: "Third-Party Sharing Without Purpose Limitation", definition: "Notice discloses sharing with third parties but does not limit the purpose of sharing.", exposure: "High — data use is unbounded", example: "Data shared with 'partners and affiliates' without further specification.", related: ["SH-002", "TRK-007"] },
  { code: "SH-002", domain: "data_sharing",        title: "Broad Sharing Language", definition: "Sharing clause uses expansive language ('business partners', 'affiliates') without enumerating categories of recipients.", exposure: "High — recipient scope is unbounded", example: "Data may be shared with our business partners worldwide.", related: ["SH-001", "TRK-007"] },
  { code: "SH-004", domain: "data_sharing",        title: "No Opt-Out for Third-Party Sharing", definition: "Notice does not offer an opt-out mechanism for data sharing with third parties.", exposure: "Elevated — consumer control absent", example: "", related: ["SH-002", "CR-003"] },
  { code: "TRK-001", domain: "tracking_cookies",   title: "Tracking Technology Disclosure Absent", definition: "Notice does not disclose the use of tracking technologies such as cookies, pixels, or fingerprinting.", exposure: "High — tracking undisclosed", example: "", related: ["TRK-007"] },
  { code: "TRK-007", domain: "tracking_cookies",   title: "Third-Party Tracking Disclosure", definition: "Clause discloses sharing of tracking data with external parties without specifying categories or contractual constraints.", exposure: "Elevated — tracking data shared without bounded purpose", example: "Third-party analytics cookies may track browsing across sites.", related: ["TRK-001", "SH-002"] },
  { code: "CR-003", domain: "consumer_rights",     title: "Opt-Out Mechanism Absent", definition: "Notice does not describe a mechanism for consumers to opt out of data processing or sharing.", exposure: "Elevated — consumer agency not supported", example: "", related: ["SH-004"] },
  { code: "CR-005", domain: "consumer_rights",     title: "Data Access Rights Not Specified", definition: "Notice acknowledges data access rights but does not describe how to exercise them.", exposure: "Moderate — rights acknowledged but inaccessible", example: "You may have the right to access your data.", related: ["CR-003"] },
  { code: "CB-001", domain: "cross_border",        title: "Cross-Border Transfer Disclosed Without Mechanism", definition: "Notice discloses international data transfers but does not specify the legal basis or safeguard.", exposure: "Elevated — transfer legality unclear", example: "Your data may be processed outside your country.", related: ["CB-002"] },
  { code: "CB-002", domain: "cross_border",        title: "Cross-Border Transfer Mechanism Absent", definition: "Cross-border data transfers are disclosed but the legal mechanism (SCCs, adequacy decision) is not stated.", exposure: "High — transfer mechanism missing", example: "", related: ["CB-001"] },
  { code: "SD-002", domain: "sensitive_data",      title: "Sensitive Data Processing Without Explicit Basis", definition: "Notice discloses processing of sensitive categories of data without citing the specific legal basis.", exposure: "High — sensitive processing unjustified", example: "Health data processed for service delivery purposes.", related: [] },
  { code: "RT-001", domain: "retention",           title: "No Retention Policy Stated", definition: "Notice contains no information about data retention periods or criteria.", exposure: "High — retention ceiling unknown", example: "", related: ["RT-003"] },
  { code: "RT-003", domain: "retention",           title: "Retention Duration Absent", definition: "No specific retention period is stated; clause defers to 'legal requirements' without citing specific periods.", exposure: "Moderate — retention ceiling vague", example: "Retained as long as required by applicable law.", related: ["RT-001"] },
  { code: "CH-001", domain: "children_teens",      title: "Children's Data Age Threshold Not Specified", definition: "Notice acknowledges restricted collection from children but does not state the age threshold.", exposure: "Elevated — threshold undefined", example: "We do not collect data from minors.", related: [] },
  { code: "AI-003", domain: "ai_automated_decisions", title: "Automated Decision Scope Undisclosed", definition: "Notice acknowledges automated processing but does not describe which decisions are automated.", exposure: "Elevated — automated scope opaque", example: "We use automated tools to improve your experience.", related: ["AI-005"] },
  { code: "AI-005", domain: "ai_automated_decisions", title: "Automated Decision Disclosure Gap", definition: "AI/ML use is acknowledged but the domains of application, logic, and opt-out rights are not disclosed.", exposure: "High — automated decisions opaque", related: ["AI-003"], example: "" },
];

function domainLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function CodexCard({ entry, expanded, onToggle }: {
  entry: CodexEntry; expanded: boolean; onToggle: () => void;
}) {
  return (
    <div style={{
      border: "1px solid var(--border)", borderRadius: "var(--radius)",
      overflow: "hidden", background: "white",
    }}>
      <button
        style={{
          width: "100%", textAlign: "left", padding: "12px 16px",
          background: expanded ? "rgba(9,35,79,0.03)" : "white",
          display: "flex", alignItems: "center", gap: 12, cursor: "pointer", border: "none",
          borderBottom: expanded ? "1px solid var(--border)" : "none",
        }}
        onClick={onToggle}
        aria-expanded={expanded}
        id={`codex-${entry.code}`}
      >
        <span className="code-chip" style={{ flexShrink: 0 }}>{entry.code}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: "0.88rem", color: "var(--navy)" }}>{entry.title}</div>
          <div className="domain-eyebrow" style={{ marginTop: 2 }}>{domainLabel(entry.domain)}</div>
        </div>
        <span style={{ color: "var(--text-muted)", fontSize: "0.85rem", flexShrink: 0 }}>
          {expanded ? "↑" : "↓"}
        </span>
      </button>
      {expanded && (
        <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <div className="section-label" style={{ marginBottom: 4 }}>Definition</div>
            <p style={{ fontSize: "0.88rem", lineHeight: 1.6, color: "var(--text-secondary)" }}>{entry.definition}</p>
          </div>
          <div>
            <div className="section-label" style={{ marginBottom: 4 }}>Exposure Signal</div>
            <p style={{ fontSize: "0.82rem", color: "var(--navy)", fontWeight: 600 }}>{entry.exposure}</p>
          </div>
          {entry.example && (
            <div>
              <div className="section-label" style={{ marginBottom: 4 }}>Example Pattern</div>
              <blockquote style={{
                borderLeft: "3px solid var(--gold)", paddingLeft: 12,
                fontStyle: "italic", fontSize: "0.82rem", color: "var(--text-muted)",
              }}>
                "{entry.example}"
              </blockquote>
            </div>
          )}
          {entry.related.length > 0 && (
            <div>
              <div className="section-label" style={{ marginBottom: 6 }}>Related Codes</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {entry.related.map(r => (
                  <button
                    key={r}
                    className="code-chip"
                    onClick={() => {
                      const el = document.getElementById(`codex-${r}`);
                      el?.scrollIntoView({ behavior: "smooth", block: "center" });
                      el?.click();
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function FindingCodex() {
  const [query, setQuery]           = useState("");
  const [domain, setDomain]         = useState<Domain | "all">("all");
  const [expanded, setExpanded]     = useState<string | null>(null);

  const filtered = useMemo(() => {
    let list = CODEX;
    if (domain !== "all") list = list.filter(e => e.domain === domain);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(e =>
        e.code.toLowerCase().includes(q) ||
        e.title.toLowerCase().includes(q) ||
        e.definition.toLowerCase().includes(q)
      );
    }
    return list;
  }, [query, domain]);

  return (
    <div>
      <PageHeader
        eyebrow="Codex"
        title="Finding Codex"
        description={`Plain-English definitions for all ${CODEX.length} finding codes used in reports — what each code means, the exposure it signals, and an example pattern. This is the source of truth behind every code chip and tooltip.`}
        actions={<span className="mock-badge" style={{ marginLeft: 0 }}>MOCK M-11 — replace with /api/codex</span>}
      />

      <div className="codex-layout" style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 24, alignItems: "start" }}>
      {/* ── Left rail: domain filter ── */}
      <div className="card codex-rail" style={{ padding: 0, overflow: "hidden", position: "sticky", top: 76 }}>
        <div className="card-head">
          <div className="card-title">Filter by domain</div>
        </div>
        <div style={{ padding: "8px 0" }}>
          <button
            style={{
              width: "100%", textAlign: "left", padding: "8px 16px",
              fontSize: "0.82rem", fontWeight: domain === "all" ? 700 : 500,
              color: domain === "all" ? "var(--navy)" : "var(--text-secondary)",
              background: domain === "all" ? "rgba(9,35,79,0.06)" : "transparent",
              border: "none", cursor: "pointer", borderLeft: domain === "all" ? "3px solid var(--navy)" : "3px solid transparent",
            }}
            onClick={() => setDomain("all")}
          >
            All domains
          </button>
          {DOMAINS.map(d => (
            <button
              key={d}
              style={{
                width: "100%", textAlign: "left", padding: "8px 16px",
                fontSize: "0.82rem", fontWeight: domain === d ? 700 : 400,
                color: domain === d ? "var(--navy)" : "var(--text-secondary)",
                background: domain === d ? "rgba(9,35,79,0.06)" : "transparent",
                border: "none", cursor: "pointer", borderLeft: domain === d ? "3px solid var(--exec-blue)" : "3px solid transparent",
                transition: "all 0.15s",
              }}
              onClick={() => setDomain(d)}
            >
              {domainLabel(d)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main: search + code list ── */}
      <div>
        <div style={{ marginBottom: 20 }}>
          <input
            type="search"
            placeholder={`Search ${CODEX.length} finding codes…`}
            value={query}
            onChange={e => setQuery(e.target.value)}
            id="codex-search-input"
            style={{
              width: "100%", padding: "10px 16px",
              border: "1.5px solid var(--border)", borderRadius: "var(--radius)",
              fontSize: "0.9rem", background: "white",
            }}
          />
        </div>

        {filtered.length === 0 ? (
          <div className="empty-state">
            <h3>No codes match "{query}"</h3>
            <p>Try searching by code (SH-002), domain, or keyword</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filtered.map(entry => (
              <CodexCard
                key={entry.code}
                entry={entry}
                expanded={expanded === entry.code}
                onToggle={() => setExpanded(expanded === entry.code ? null : entry.code)}
              />
            ))}
          </div>
        )}

      </div>
      </div>
    </div>
  );
}
