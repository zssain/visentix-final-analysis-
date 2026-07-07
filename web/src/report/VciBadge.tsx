/** VCI confidence affordance — shown next to every score. */

// Text tones derived from the token palette (same dark tones used by badge-* in index.css)
const VCI_COLORS: Record<string, string> = {
  very_high: "#0d6b5c", // teal text tone — matches badge-teal / badge-approved
  high: "#005FA3",      // exec-blue token
  moderate: "#7a5c20",  // gold text tone — matches badge-gold / badge-draft
  low: "#b91c1c",       // red text tone — matches badge-high
  very_low: "#b91c1c",
};

interface VciBadgeProps {
  label: string;
}

export function VciBadge({ label }: VciBadgeProps) {
  const color = VCI_COLORS[label] ?? "var(--text-muted)";
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
