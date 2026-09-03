// F-015 (PROPOSED) peer-position density — the reflected weighted cohort curve,
// the organization's marker on it, the individual peer points as a rug beneath,
// and the confidence interval on the position. It reads STORED values only and
// performs no statistics (Hard Rule 4 / DIR-008) — every number here was frozen
// into the snapshot by the scoring engine.
//
// What it must NOT say (OD-14 / OD-29, both open): no comparative peer-position
// word ("above/below average", "top quartile"), and no standard-deviation
// language. It states the position and its interval as plain figures only.
//
// Colours come from theme tokens (var(--…)); never a literal hex (check_colors).

type PeerPoint = { x: number; weight: number };

export type PeerDistributionPayload = {
  proposed?: boolean;
  suppressed?: boolean;
  suppression_reason?: string | null;
  n_eff?: number;
  n_eff_int?: number;
  percentile?: number;
  ci_lower?: number | null;
  ci_upper?: number | null;
  alpha?: number;
  ci_one_sided?: boolean;
  grid?: number[];
  density?: number[];
  peers?: PeerPoint[];
  cohort_date?: string;
};

const W = 420;
const H = 150;
const PAD_L = 12;
const PAD_R = 12;
const PAD_T = 14;
const PAD_B = 22; // room for the rug + baseline

function xScale(x: number): number {
  return PAD_L + (Math.max(0, Math.min(100, x)) / 100) * (W - PAD_L - PAD_R);
}

function reasonText(reason: string | null | undefined): string {
  if (reason && reason.startsWith("n_eff_below_cohort_floor")) {
    return "The peer cohort is too small to draw a reliable distribution, so the curve is withheld. The percentile above still stands, read with the low-confidence label.";
  }
  if (reason === "zero_dispersion") {
    return "Every comparable peer scored identically here, so there is no spread to plot. The curve is withheld rather than drawn as a fabricated shape.";
  }
  return "A stored peer distribution is not available for this assessment.";
}

export function PeerDistribution({ data }: { data: PeerDistributionPayload | null | undefined }) {
  // Honest absence — no curve invented where the data does not support one.
  if (!data || data.suppressed || !data.grid?.length || !data.density?.length) {
    return (
      <figure className="pd-figure" style={{ margin: "18px 0 0" }}>
        <figcaption
          style={{
            padding: "10px 12px",
            background: "var(--soft-white)",
            color: "var(--text-muted)",
            fontSize: "0.8rem",
            borderRadius: "var(--radius)",
          }}
        >
          {reasonText(data?.suppression_reason)}
        </figcaption>
      </figure>
    );
  }

  const grid = data.grid;
  const density = data.density;
  const peers = data.peers ?? [];
  const percentile = typeof data.percentile === "number" ? data.percentile : null;
  const ciLo = typeof data.ci_lower === "number" ? data.ci_lower : null;
  const ciHi = typeof data.ci_upper === "number" ? data.ci_upper : null;
  const nEff = data.n_eff_int ?? Math.floor(data.n_eff ?? 0);
  const asOf = data.cohort_date ?? "—";
  const alphaPct = typeof data.alpha === "number" ? Math.round((1 - data.alpha) * 100) : 95;

  const maxD = Math.max(...density) || 1;
  const baseY = H - PAD_B;
  const yScale = (d: number) => baseY - (d / maxD) * (H - PAD_T - PAD_B);

  const path = grid
    .map((gx, i) => `${i === 0 ? "M" : "L"} ${xScale(gx).toFixed(2)} ${yScale(density[i]).toFixed(2)}`)
    .join(" ");
  const areaPath = `${path} L ${xScale(grid[grid.length - 1]).toFixed(2)} ${baseY} L ${xScale(grid[0]).toFixed(2)} ${baseY} Z`;

  const ariaLabel =
    `Peer-position distribution over ${nEff} effective peers.` +
    (percentile !== null ? ` This organization at the ${percentile.toFixed(1)}th percentile.` : "") +
    (ciLo !== null && ciHi !== null ? ` ${alphaPct}% interval from ${ciLo.toFixed(1)} to ${ciHi.toFixed(1)}.` : "");

  return (
    <figure className="pd-figure" style={{ margin: "18px 0 0" }}>
      <figcaption
        style={{
          fontSize: "0.68rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.09em",
          color: "var(--text-muted)",
          marginBottom: 6,
        }}
      >
        Where this organization sits in its peer cohort
      </figcaption>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label={ariaLabel}
        style={{ display: "block", maxWidth: 520 }}
      >
        {/* Confidence interval band on the position */}
        {ciLo !== null && ciHi !== null && (
          <rect
            x={xScale(ciLo)}
            y={PAD_T}
            width={Math.max(0, xScale(ciHi) - xScale(ciLo))}
            height={baseY - PAD_T}
            fill="color-mix(in oklab, var(--navy) 12%, transparent)"
          />
        )}

        {/* Density: filled area + curve */}
        <path d={areaPath} fill="color-mix(in oklab, var(--navy) 8%, transparent)" />
        <path d={path} fill="none" stroke="var(--navy)" strokeWidth={1.5} />

        {/* Baseline */}
        <line x1={PAD_L} y1={baseY} x2={W - PAD_R} y2={baseY} stroke="var(--border)" strokeWidth={1} />

        {/* Rug — the individual peer points. Required: at a handful of effective
            peers a smooth curve alone overstates the evidence; the visible points
            are what stop it. */}
        {peers.map((p, i) => (
          <line
            key={i}
            x1={xScale(p.x)}
            y1={baseY}
            x2={xScale(p.x)}
            y2={baseY + 6}
            stroke="var(--text-muted)"
            strokeWidth={1}
          />
        ))}

        {/* Organization marker */}
        {percentile !== null && (
          <line
            x1={xScale(percentile)}
            y1={PAD_T}
            x2={xScale(percentile)}
            y2={baseY + 6}
            stroke="var(--navy)"
            strokeWidth={2}
          />
        )}
      </svg>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.72rem",
          color: "var(--text-muted)",
          marginTop: 4,
        }}
      >
        <span>0th</span>
        {percentile !== null && (
          <span style={{ color: "var(--navy)", fontWeight: 700 }}>
            This organization · {percentile.toFixed(1)}th percentile
          </span>
        )}
        <span>100th</span>
      </div>

      <figcaption className="pd-note" style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--text-muted)" }}>
        {ciLo !== null && ciHi !== null ? (
          <>
            The shaded band is the {alphaPct}% confidence interval on this position
            ({ciLo.toFixed(1)}th–{ciHi.toFixed(1)}th percentile). The ticks below the curve are the
            individual comparable organizations.{" "}
          </>
        ) : (
          <>The ticks below the curve are the individual comparable organizations.{" "}</>
        )}
        Based on {nEff} effective peers, as of {asOf}. This distribution is a
        provisional view pending expert ratification.
      </figcaption>
    </figure>
  );
}
