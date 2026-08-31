import { cn } from "@/lib/utils";

/**
 * A small state dot.
 *
 * Replaces `.live-dot`, which had three problems: it pulsed forever while
 * ignoring `prefers-reduced-motion`, it hard-coded emerald outside the token
 * layer, and its green collided with green-means-good on the standing scale.
 * Here the colour says what KIND of state this is (live / stopped), never how
 * good a score is, and the pulse stops for readers who ask it to.
 */
export function StatusDot({
  state = "live", label, className,
}: { state?: "live" | "stopped"; label?: string; className?: string }) {
  const color = state === "live" ? "var(--verified)" : "var(--standing-bad)";
  return (
    <span className={cn("relative inline-flex size-2.5 shrink-0", className)} role="img" aria-label={label ?? state}>
      {state === "live" && (
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 motion-reduce:hidden"
          style={{ background: color }}
          aria-hidden="true"
        />
      )}
      <span className="relative inline-flex size-2.5 rounded-full" style={{ background: color }} aria-hidden="true" />
    </span>
  );
}
