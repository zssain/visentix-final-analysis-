/**
 * ExplainPanel — side drawer showing how a score/finding/narrative was produced.
 *
 * Renders: formula sentence + version, input table, VCI components as bars,
 * source refs, and narrative provenance badge.
 */
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";
import { Badge } from "@/components/ui/badge";

export interface ExplainPanelProps {
  explanation: Record<string, unknown>;
  kind: "score" | "finding" | "narrative";
  label?: string;
  onClose: () => void;
}

function VciComponents({ components }: { components: Record<string, number> }) {
  const data = Object.entries(components).map(([name, value]) => ({
    name,
    value: Math.round(value * 100),
  }));

  if (data.length === 0) return null;

  return (
    <div data-testid="vci-components" style={{ width: "100%", height: 160 }}>
      <h4 style={{ margin: "8px 0 4px" }}>What drives this confidence</h4>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
          <XAxis type="number" domain={[0, 100]} />
          <YAxis type="category" dataKey="name" width={80} />
          <Bar dataKey="value" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.value >= 70 ? "var(--chart-3)" : d.value >= 40 ? "var(--chart-2)" : "var(--chart-1)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function InputsTable({ inputs }: { inputs: Record<string, unknown> }) {
  const entries = Object.entries(inputs).filter(
    ([, v]) => typeof v !== "object" || v === null,
  );
  if (entries.length === 0) return null;

  return (
    <table data-testid="inputs-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85em" }}>
      <thead>
        <tr style={{ background: "var(--muted)" }}>
          <th style={thStyle}>Input</th>
          <th style={thStyle}>Value</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, val]) => (
          <tr key={key}>
            <td style={tdStyle}>{key.replace(/_/g, " ")}</td>
            <td style={tdStyle}>{String(val)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ScoreExplanation({ explanation }: { explanation: Record<string, unknown> }) {
  const confidence = (explanation.confidence ?? {}) as Record<string, unknown>;
  const components = (confidence.components ?? {}) as Record<string, number>;
  const inputs = (explanation.inputs ?? {}) as Record<string, unknown>;
  const sourceRefs = (explanation.source_refs ?? {}) as Record<string, unknown>;

  return (
    <>
      <div data-testid="formula-sentence" className="explain-formula">
        <strong>Formula:</strong> {explanation.formula_plain as string}
      </div>
      <div className="explain-version" style={{ fontSize: "0.8em", color: "var(--muted-foreground)" }}>
        Version: {explanation.formula_version as string}
      </div>

      <div style={{ margin: "12px 0" }}>
        <strong>Score:</strong> {String(explanation.score)}
      </div>

      <h4 style={{ margin: "12px 0 4px" }}>Inputs (source lineage)</h4>
      <InputsTable inputs={inputs} />

      <div style={{ margin: "12px 0" }}>
        <strong>Confidence:</strong> {String(confidence.vci)} ({confidence.label as string})
        <div style={{ fontSize: "0.85em", color: "var(--muted-foreground)" }}>
          {confidence.guidance as string}
        </div>
      </div>

      <VciComponents components={components} />

      {sourceRefs.notice_id && (
        <div style={{ margin: "8px 0", fontSize: "0.85em" }}>
          <strong>Source:</strong> Notice {(sourceRefs.notice_id as string).slice(0, 12)},
          {" "}{String(sourceRefs.clause_count)} clauses
        </div>
      )}
    </>
  );
}

function FindingExplanation({ explanation }: { explanation: Record<string, unknown> }) {
  const clauseIds = (explanation.triggering_clause_ids ?? []) as string[];

  return (
    <>
      <div style={{ margin: "8px 0" }}>
        <strong>Domain:</strong> {(explanation.domain as string)?.replace(/_/g, " ")}
        {" · "}
        <strong>Severity:</strong>{" "}
        <span className={`tier-${explanation.severity}`}>{explanation.severity as string}</span>
        {" · "}
        <strong>Score:</strong> {String(explanation.score)}
      </div>

      <div data-testid="how-selected" className="explain-formula">
        <strong>How selected:</strong> {explanation.how_selected as string}
      </div>

      <div style={{ fontSize: "0.8em", color: "var(--muted-foreground)", margin: "8px 0" }}>
        Formula version: {explanation.formula_version as string}
      </div>

      {clauseIds.length > 0 && (
        <div style={{ fontSize: "0.85em", margin: "8px 0" }}>
          <strong>Triggering clauses:</strong> {clauseIds.length} clause(s)
        </div>
      )}
    </>
  );
}

function NarrativeExplanation({ explanation }: { explanation: Record<string, unknown> }) {
  const numbersFrom = (explanation.numbers_from ?? []) as string[];

  return (
    <>
      <div data-testid="narrative-provenance" className="explain-formula">
        {explanation.provenance as string}
      </div>

      <div style={{ margin: "12px 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(() => {
          // GRD-002: honest three-state receipt. "passed" → green; a missing
          // or "not_recorded" status → neutral (never a green pass, never a red
          // fail); an explicit non-pass status → red. Red is reserved for a real
          // failure, per the design system.
          const g = (explanation.guardrail as string) ?? "not_recorded";
          const isPass = g === "passed";
          const isAbsent = g === "not_recorded" || !explanation.guardrail;
          const bg = isPass ? "color-mix(in oklab, var(--standing-good) 12%, var(--card))" : isAbsent ? "var(--muted)" : "color-mix(in oklab, var(--standing-bad) 8%, var(--card))";
          const fg = isPass ? "var(--standing-good)" : isAbsent ? "var(--muted-foreground)" : "var(--standing-bad)";
          return (
            <Badge variant="secondary" data-testid="guardrail-badge" className="explain-badge" style={{ background: bg, color: fg, padding: "2px 8px", borderRadius: 4, fontSize: "0.85em", fontWeight: 600, }} title={ isAbsent ? "Guardrail status was not recorded for this snapshot." : undefined }>
              {isAbsent
                ? "Guardrail status was not recorded for this snapshot."
                : `Guardrail: ${g}`}
            </Badge>
          );
        })()}
        <Badge variant="secondary" data-testid="llm-badge" className="explain-badge" style={{ background: "color-mix(in oklab, var(--primary) 8%, var(--card))", color: "var(--primary)", padding: "2px 8px", borderRadius: 4, fontSize: "0.85em", fontWeight: 600, }}>
          {explanation.llm_used ? "LLM rephrased" : "Template used"}
        </Badge>
      </div>

      {numbersFrom.length > 0 && (
        <div style={{ fontSize: "0.85em", margin: "8px 0" }}>
          <strong>Numbers computed by:</strong> {numbersFrom.join(", ").toUpperCase()}
        </div>
      )}
    </>
  );
}

export function ExplainPanel({ explanation, kind, label, onClose }: ExplainPanelProps) {
  return (
    <div
      data-testid="explain-panel"
      className="explain-panel-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", top: 0, right: 0, bottom: 0, left: 0,
        background: "rgba(0,0,0,0.3)", zIndex: 1000,
        display: "flex", justifyContent: "flex-end",
      }}
    >
      <div
        className="explain-panel"
        style={{
          width: 420, maxWidth: "90vw", background: "var(--card)", height: "100%",
          overflowY: "auto", padding: "24px 20px", boxShadow: "-2px 0 8px rgba(0,0,0,0.1)",
        }}
      >
        <div className="flex justify-between items-center mb-4">
          <h3 style={{ margin: 0, color: "var(--primary)" }}>
            {label ?? (kind === "score" ? "Score" : kind === "finding" ? "Finding" : "Narrative")}
          </h3>
          <button
            data-testid="explain-close"
            onClick={onClose}
            style={{
              background: "none", border: "none", fontSize: "1.2em",
              cursor: "pointer", color: "var(--muted-foreground)",
            }}
          >
            &times;
          </button>
        </div>

        {kind === "score" && <ScoreExplanation explanation={explanation} />}
        {kind === "finding" && <FindingExplanation explanation={explanation} />}
        {kind === "narrative" && <NarrativeExplanation explanation={explanation} />}

      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = { border: "1px solid var(--border)", padding: "6px 10px", textAlign: "left" };
const tdStyle: React.CSSProperties = { border: "1px solid var(--border)", padding: "6px 10px" };
