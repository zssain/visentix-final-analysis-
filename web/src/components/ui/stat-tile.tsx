import * as React from "react";
import { cn } from "@/lib/utils";
import { AnimatedNumber } from "./animated-number";

/**
 * A single headline figure with its label.
 *
 * This is deliberately NOT a chart. A single current value against a label is
 * a stat tile; rendering it as a one-bar bar chart spends axis chrome to say
 * what one large number says better.
 *
 * `tone` names a STANDING, never a colour — the caller decides what the number
 * means, the token layer decides what that looks like.
 */
export function StatTile({
  label, value, decimals = 0, tone = "neutral", hint, className,
}: {
  label: string;
  value: number | null | undefined;
  decimals?: number;
  tone?: "neutral" | "good" | "mid" | "bad";
  hint?: React.ReactNode;
  className?: string;
}) {
  const toneClass = {
    neutral: "text-foreground",
    good: "text-[var(--standing-good)]",
    mid: "text-[var(--standing-mid)]",
    bad: "text-[var(--standing-bad)]",
  }[tone];

  return (
    <div className={cn("flex flex-col gap-1 min-w-[92px]", className)}>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className={cn("font-data text-2xl font-bold leading-none", toneClass)}>
        {typeof value === "number"
          ? <AnimatedNumber value={value} decimals={decimals} />
          : /* honest absence — never a zero standing in for "not measured" */ "—"}
      </span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}
