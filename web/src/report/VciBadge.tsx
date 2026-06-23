/** VCI confidence affordance — shown next to every score. */

const VCI_COLORS: Record<string, string> = {
  very_high: "#065f46",
  high: "#1e40af",
  moderate: "#92400e",
  low: "#991b1b",
  very_low: "#7f1d1d",
};

interface VciBadgeProps {
  label: string;
}

export function VciBadge({ label }: VciBadgeProps) {
  const color = VCI_COLORS[label] ?? "#6b7280";
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
    >
      {label.replace("_", " ")}
    </span>
  );
}
