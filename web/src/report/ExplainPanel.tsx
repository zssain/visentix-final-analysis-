/**
 * ExplainPanel — side drawer showing how a score/finding/narrative was produced.
 *
 * Renders: formula sentence + version, input table, VCI components as bars,
 * source refs, and narrative provenance badge.
 */
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

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
      <h4 style={{ margin: "8px 0 4px" }}>VCI Components</h4>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
          <XAxis type="number" domain={[0, 100]} />
          <YAxis type="category" dataKey="name" width={80} />
          <Bar dataKey="value" isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.value >= 70 ? "#22c55e" : d.value >= 40 ? "#f59e0b" : "#dc2626"}
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
        <tr style={{ background: "#f3f4f6" }}>
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
      <div className="explain-version" style={{ fontSize: "0.8em", color: "#6b7280" }}>
        Version: {explanation.formula_version as string}
      </div>

      <div style={{ margin: "12px 0" }}>
        <strong>Score:</strong> {String(explanation.score)}
      </div>

      <h4 style={{ margin: "12px 0 4px" }}>Inputs (source lineage)</h4>
      <InputsTable inputs={inputs} />

      <div style={{ margin: "12px 0" }}>
        <strong>VCI:</strong> {String(confidence.vci)} ({confidence.label as string})
        <div style={{ fontSize: "0.85em", color: "#6b7280" }}>
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

      <div style={{ fontSize: "0.8em", color: "#6b7280", margin: "8px 0" }}>
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
        <span
          data-testid="guardrail-badge"
          className="explain-badge"
          style={{
            background: explanation.guardrail === "passed" ? "#dcfce7" : "#fef2f2",
            color: explanation.guardrail === "passed" ? "#166534" : "#991b1b",
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: "0.85em",
            fontWeight: 600,
          }}
        >
          Guardrail: {explanation.guardrail as string}
        </span>
        <span
          data-testid="llm-badge"
          className="explain-badge"
          style={{
            background: "#eff6ff",
            color: "#1e40af",
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: "0.85em",
            fontWeight: 600,
          }}
        >
          {explanation.llm_used ? "LLM rephrased" : "Template used"}
        </span>
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
          width: 420, maxWidth: "90vw", background: "#fff", height: "100%",
          overflowY: "auto", padding: "24px 20px", boxShadow: "-2px 0 8px rgba(0,0,0,0.1)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0, color: "#0f3460" }}>
            {label ?? (kind === "score" ? "Score" : kind === "finding" ? "Finding" : "Narrative")}
          </h3>
          <button
            data-testid="explain-close"
            onClick={onClose}
            style={{
              background: "none", border: "none", fontSize: "1.2em",
              cursor: "pointer", color: "#6b7280",
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

const thStyle: React.CSSProperties = { border: "1px solid #d1d5db", padding: "6px 10px", textAlign: "left" };
const tdStyle: React.CSSProperties = { border: "1px solid #d1d5db", padding: "6px 10px" };
