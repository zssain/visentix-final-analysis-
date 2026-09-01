/**
 * PageHeader — standard header for every routed screen.
 *
 * Eyebrow = where you are (matches the nav label), title = the screen,
 * description = one plain-language sentence saying what the screen does.
 * `actions` renders on the right: status chips, counts, primary CTA.
 *
 * Built to the SAME recipe as the sidebar — same radius, translucency, blur,
 * border, wash, hairline and top offset — so the two read as one piece of
 * chrome rather than two adjacent surfaces.
 *
 * TYPOGRAPHY. The title wears the display face at the top of the heading scale
 * (`design-system.md` §4): display for headings, sans for body and labels, data
 * for figures. One rule, so a heading never announces itself by being the odd
 * font on the screen.
 *
 * All decoration is `aria-hidden`; the words, the heading level and the reading
 * order are the component's only content.
 */
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("relative mb-7 isolate", className)}>
      <header className="relative flex flex-wrap items-start justify-between gap-x-6 gap-y-4 overflow-hidden rounded-2xl border px-6 py-6 shadow-lg backdrop-blur-xl md:px-7 md:py-7 bg-card supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--card)_72%,transparent)] print:border print:bg-card print:shadow-none print:backdrop-blur-none">
        {/* Wash. Anchored top-left behind the title so it reads as light falling
            on the panel rather than a tinted box. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 print:hidden"
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
            <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {eyebrow}
            </span>
          </div>
          <h1 className="font-display text-[1.75rem] font-semibold leading-[1.15] tracking-[-0.02em] md:text-[2.125rem]">
            {title}
          </h1>
          <p className="m-0 max-w-prose text-sm leading-relaxed text-muted-foreground">
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
