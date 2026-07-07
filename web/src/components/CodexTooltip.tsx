import { useState, useCallback } from "react";
import "./furniture.css";

// [MOCK M-11] — real entries come from /api/codex + finding_type catalog table
const CODEX_MOCK: Record<string, { title: string; definition: string; exposure: string; related: string[] }> = {
  "TRK-007": {
    title: "Third-Party Tracking Disclosure",
    definition: "Clause discloses sharing of tracking data with external parties without specifying categories or contractual constraints.",
    exposure: "Elevated — tracking data shared without bounded purpose",
    related: ["TRK-001", "SH-002"],
  },
  "SH-002": {
    title: "Broad Sharing Language",
    definition: "Sharing clause uses expansive language ('business partners', 'affiliates') without enumerating categories of recipients.",
    exposure: "High — recipient scope is unbounded",
    related: ["TRK-007", "SH-004"],
  },
  "RT-003": {
    title: "Retention Duration Absent",
    definition: "No specific retention period is stated; clause defers to 'legal requirements' without citing specific periods.",
    exposure: "Moderate — retention ceiling unknown",
    related: ["RT-001"],
  },
  "CB-002": {
    title: "Cross-Border Transfer Mechanism Absent",
    definition: "Cross-border data transfers are disclosed but the legal mechanism (SCCs, adequacy decision, etc.) is not stated.",
    exposure: "Elevated — transfer legality unclear",
    related: ["CB-001"],
  },
  "AI-005": {
    title: "Automated Decision Disclosure Gap",
    definition: "AI/ML use is acknowledged but the domains of application, logic, and opt-out rights are not disclosed.",
    exposure: "High — automated decisions opaque",
    related: ["AI-001", "AI-003"],
  },
};

interface CodexTooltipProps {
  code: string;
  children?: React.ReactNode;
}

export function CodexTooltip({ code, children }: CodexTooltipProps) {
  const [visible, setVisible] = useState(false);
  const entry = CODEX_MOCK[code];

  const show = useCallback(() => setVisible(true), []);
  const hide = useCallback(() => setVisible(false), []);

  return (
    <div
      className="codex-trigger"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      tabIndex={0}
      role="button"
      aria-label={`${code} — ${entry?.title ?? "Finding code"}`}
      aria-expanded={visible}
    >
      {children ?? <span className="code-chip">{code}</span>}
      {visible && entry && (
        <div className="codex-tooltip" role="tooltip">
          <div className="ct-code">{code}</div>
          <div className="ct-title">{entry.title}</div>
          <div className="ct-def">{entry.definition}</div>
          <div className="ct-related">
            Exposure: {entry.exposure}
            {entry.related.length > 0 && (
              <> · Related: {entry.related.join(", ")}</>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
