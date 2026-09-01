/**
 * PageHeader — standard header for every routed screen.
 *
 * Eyebrow = where you are (matches the nav label), title = the screen,
 * description = one plain-language sentence saying what the screen does.
 * `actions` renders on the right: status chips, counts, primary CTA.
 *
 * PRESENTATION (2026-09-01). It was three stacked text blocks and a plain grey
 * rule — identical on all thirteen screens that use it, and carrying none of
 * the language the rest of the product now speaks. It is now a panel built to
 * the SAME recipe as the sidebar: the same radius, the same translucency, the
 * same blur, the same border and the same 12px top offset, so the two read as
 * one piece of chrome rather than two unrelated surfaces.
 *
 * It sticks, and it minimises as you scroll: the description and the wash go,
 * the title steps down, the padding tightens. What never goes is where you are
 * (eyebrow + title) or what you can do (actions) — a header that hides its own
 * controls on scroll is worse than one that does not stick at all.
 *
 * All the decoration is `aria-hidden`, and the words, the heading level and the
 * reading order never change — including when it collapses. Nothing here alters
 * what a screen says or how it is announced.
 */
import { cn } from "@/lib/utils";
import { useScrolled } from "@/lib/useScrolled";

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  const compact = useScrolled();

  return (
    <div
      className={cn(
        /* Below the mobile top bar (fixed, 56px), level with the sidebar card
           on desktop. Sticking to `top-3` on mobile would slide the header
           under that bar and hide the title behind it. */
        "sticky top-[calc(3.5rem+0.75rem)] md:top-3 z-30 mb-7 isolate",
        /* Print gets a plain, static header: a pinned translucent panel is
           screen furniture and would otherwise be stamped onto every page. */
        "print:static print:mb-4",
        className,
      )}
    >
      <header
        className={cn(
          "relative flex flex-wrap items-start justify-between gap-x-6 overflow-hidden",
          /* Same radius, border, blur and translucency as the sidebar card. The
             `supports-` guard keeps the fallback honest: where backdrop-filter
             is unavailable the panel is opaque rather than a washed-out tint
             with unreadable text over the content scrolling behind it. */
          "rounded-2xl border shadow-lg backdrop-blur-xl",
          "bg-card supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--card)_72%,transparent)]",
          "transition-[padding,gap] duration-200 ease-out motion-reduce:transition-none",
          "print:border print:bg-card print:shadow-none print:backdrop-blur-none",
          compact ? "gap-y-2 px-5 py-3 md:px-6" : "gap-y-4 px-6 py-6 md:px-7 md:py-7",
        )}
      >
        {/* Wash. Anchored top-left behind the title so it reads as light falling
            on the panel rather than a tinted box. It fades out when the header
            collapses — at that height it is a smear rather than a gradient. */}
        <div
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-0 -z-10 transition-opacity duration-200",
            "motion-reduce:transition-none print:hidden",
            compact ? "opacity-0" : "opacity-100",
          )}
          style={{
            background:
              "radial-gradient(70% 120% at 0% 0%, color-mix(in oklab, var(--verified) 10%, transparent) 0%, transparent 62%)," +
              "radial-gradient(55% 110% at 100% 0%, color-mix(in oklab, var(--provisional) 8%, transparent) 0%, transparent 60%)",
          }}
        />

        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex items-center gap-2">
            {/* The same teal that marks the selected nav item, so the eyebrow
                and the sidebar agree about where you are. */}
            <span
              aria-hidden="true"
              className="h-3 w-[3px] shrink-0 rounded-full bg-[var(--verified)]"
            />
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {eyebrow}
            </span>
          </div>
          <h1
            className={cn(
              "font-display font-semibold leading-tight tracking-tight",
              "transition-[font-size] duration-200 ease-out motion-reduce:transition-none",
              compact ? "text-xl md:text-2xl" : "text-2xl md:text-[2rem]",
            )}
          >
            {title}
          </h1>
          {/* The description is context, not identity: it is the one part that
              can go when space is short. `hidden` rather than height-animated,
              so a screen reader is not read a sentence that is visually absent. */}
          <p
            className={cn(
              "m-0 max-w-prose text-sm leading-relaxed text-muted-foreground",
              compact && "hidden print:block",
            )}
          >
            {description}
          </p>
        </div>

        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}

        {/* Brand hairline along the panel's top edge, clipped to the same curve
            by the parent's overflow-hidden. It used to sit UNDER the panel as a
            full-width rule, which left a visible notch at each bottom corner —
            a straight line drawn edge to edge cannot meet a rounded border. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, var(--verified) 0%, var(--provisional) 26%, transparent 72%)",
            opacity: 0.7,
          }}
        />
      </header>
    </div>
  );
}
