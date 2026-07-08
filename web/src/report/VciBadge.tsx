/** VCI confidence badge — shows spec 5-band label. */

// Map both old underscore labels and new spec labels to display text
const VCI_DISPLAY: Record<string, string> = {
  very_high: "Very High",
  "Very High": "Very High",
  high: "High",
  "High": "High",
  moderate: "Moderate",
  "Moderate": "Moderate",
  low: "Low",
  "Low": "Low",
  very_low: "Very Low",
  "Very Low": "Very Low",
};

const VCI_COLORS: Record<string, string> = {
  "Very High": "#0d6b5c",
  "High": "#005FA3",
  "Moderate": "#7a5c20",
  "Low": "#b91c1c",
  "Very Low": "#b91c1c",
};

interface VciBadgeProps {
  label: string;
  guidance?: string;
}

export function VciBadge({ label, guidance }: VciBadgeProps) {
  const display = VCI_DISPLAY[label] ?? label.replace(/_/g, " ");
  const color = VCI_COLORS[display] ?? "var(--text-muted)";
  return (
    <span
      className="vci-badge"
      style={{
        display: "inline-block",
        padding: "1px 8px",
        borderRadius: 4,
        fontSize: "0.8em",
        fontWeight: 600,
        color,
        border: `1px solid ${color}`,
        marginLeft: 6,
      }}
      data-testid="vci-badge"
      title={guidance || `Confidence: ${display}`}
    >
      {display}
    </span>
  );
}
