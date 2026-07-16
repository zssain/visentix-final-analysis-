/**
 * F13 — Framework Crosswalk Explorer · UI (built against mocks, M-25).
 *
 * Shows how the 8 disclosure domains + their finding codes RELATE TO the
 * NIST Privacy Framework, ISO 27701, GDPR, and CCPA/CPRA. Descriptive-only —
 * references, never compliance verdicts (business-logic §2, F13 guardrail).
 * Public route; data mocked ahead of the framework_reference backend + OD-01
 * copy sign-off.
 */
import { Fragment, useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import {
  FRAMEWORKS, DOMAINS, MAPPINGS, cellMappings, type FrameworkId,
} from "./mockData";
import "../../components/furniture.css";
import "./crosswalk.css";

export function FrameworkCrosswalk() {
  const [activeFw, setActiveFw] = useState<FrameworkId | "all">("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const visibleFrameworks = activeFw === "all"
    ? FRAMEWORKS
    : FRAMEWORKS.filter(f => f.id === activeFw);

  const toggleDomain = (id: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <PageHeader
        eyebrow="Crosswalk"
        title="Framework Crosswalk"
        description="How Visentix's disclosure domains and finding codes relate to the frameworks you already report against. Descriptive references — not compliance determinations."
        actions={<IntelligenceMark />}
      />

      {/* Descriptive-only guardrail banner (AC-5) */}
      <div className="xw-banner">
        <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>ⓘ</span>
        <span>
          <b>These are descriptive references, not compliance determinations.</b> A mapping means a domain or
          finding code <i>relates to</i> a framework provision — it does not state that any organisation meets,
          satisfies, or fails it. Citations are references, not legal advice.
        </span>
      </div>

      {/* Framework filter (AC-2) */}
      <div className="xw-filters">
        <button className={`xw-filter ${activeFw === "all" ? "on" : ""}`} aria-pressed={activeFw === "all"} onClick={() => setActiveFw("all")}>
          All frameworks
        </button>
        {FRAMEWORKS.map(f => (
          <button key={f.id} className={`xw-filter ${activeFw === f.id ? "on" : ""}`} aria-pressed={activeFw === f.id} onClick={() => setActiveFw(f.id)}>
            {f.name}
          </button>
        ))}
      </div>

      {/* Matrix (AC-1, AC-6) */}
      <div className="xw-scroll">
        <table className="xw-matrix">
          <thead>
            <tr>
              <th style={{ minWidth: 170 }}>Domain</th>
              {visibleFrameworks.map(f => <th key={f.id}>{f.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {DOMAINS.map(d => {
              const isOpen = expanded.has(d.id);
              return (
                <Fragment key={d.id}>
                  <tr>
                    <td className="xw-domain-cell">
                      <span className="xw-domain-name">
                        <span className="xw-domain-id">{d.id}</span>{d.name}
                      </span>
                      <button className="xw-domain-toggle" aria-expanded={isOpen} onClick={() => toggleDomain(d.id)}>
                        {isOpen ? "Hide finding codes" : `Show ${d.codes.length} finding codes`}
                      </button>
                    </td>
                    {visibleFrameworks.map(f => {
                      const cells = cellMappings(d.id, f.id).filter(m => m.code === null);
                      return (
                        <td key={f.id}>
                          {cells.length === 0 ? (
                            <span className="xw-none">— no direct reference</span>
                          ) : (
                            cells.map((m, i) => (
                              <div key={i} className="xw-citation">
                                <div className="xw-cite-ref">{m.citation}</div>
                                <div className="xw-cite-note">{m.note}</div>
                              </div>
                            ))
                          )}
                        </td>
                      );
                    })}
                  </tr>

                  {isOpen && (
                    <tr>
                      <td colSpan={visibleFrameworks.length + 1} style={{ background: "var(--soft-white)" }}>
                        <div style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 8 }}>
                          {d.name} · finding codes and what they relate to
                        </div>
                        {d.codes.map(code => {
                          const codeMaps = MAPPINGS.filter(m => m.domainId === d.id && m.code === code
                            && (activeFw === "all" || m.framework === activeFw));
                          return (
                            <div key={code} className="xw-code-line">
                              <span className="xw-code-chip">{code}</span>
                              <span style={{ flex: 1 }}>
                                {codeMaps.length === 0 ? (
                                  <span className="xw-none">no code-specific reference{activeFw === "all" ? "" : " for this framework"}</span>
                                ) : (
                                  codeMaps.map((m, i) => (
                                    <span key={i} style={{ display: "block", marginBottom: 3 }}>
                                      <span className="xw-cite-ref">{m.citation}</span>
                                      <span className="xw-cite-note"> — {m.note}</span>
                                    </span>
                                  ))
                                )}
                              </span>
                            </div>
                          );
                        })}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
