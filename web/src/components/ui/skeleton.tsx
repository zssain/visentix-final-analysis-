import { cn } from "@/lib/utils"

/**
 * A placeholder for content that is loading.
 *
 * Two things it must do that the stock version did not:
 *
 * ANNOUNCE ITSELF. A pulsing grey box is invisible to a screen reader, so the
 * page went from silence to a full result with nothing said in between.
 * `role="status"` + `aria-busy` means assistive tech reports that something is
 * loading, and `aria-hidden` on the boxes keeps the shapes themselves out of
 * the reading order.
 *
 * STOP MOVING UNDER REDUCED MOTION. `animate-pulse` runs forever; §7 permits
 * arrival animation, not a permanent one, and an indefinite pulse is exactly
 * the kind of motion `prefers-reduced-motion` exists for. It holds still at a
 * visible tint instead of disappearing — the placeholder still has to read as
 * a placeholder.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-md bg-accent motion-reduce:animate-none motion-reduce:opacity-80",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Wraps a group of skeletons so the wait is announced once, not once per box.
 * `label` says what is loading — "Loading assessments", not "Loading".
 */
function SkeletonGroup({ label, className, children, ...props }: React.ComponentProps<"div"> & { label: string }) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className} {...props}>
      {children}
    </div>
  )
}

export { Skeleton, SkeletonGroup }
