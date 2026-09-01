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
 * TYPOGRAPHY. The UI sans. The display serif belongs to the REPORT — it is the
 * artifact a customer forwards, and its editorial voice is the point. Wearing
 * it in the application chrome made every screen look like a document it is
 * not, and made a serif page title outweigh the content beneath it
 * (`design-system.md` §1).
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
    <div className={cn("relative mb-5 isolate", className)}>
      <header className="relative flex flex-wrap items-start justify-between gap-x-6 gap-y-3 overflow-hidden rounded-xl border px-5 py-4 backdrop-blur-xl md:px-6 md:py-5 bg-card supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--card)_72%,transparent)] print:border print:bg-card print:backdrop-blur-none">
        {/* Wash. Anchored top-left behind the title so it reads as light falling
            on the panel rather than a tinted box. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 print:hidden"
          style={{
            background:
              "radial-gradient(70% 120% at 0% 0%, color-mix(in oklab, var(--verified) 7%, transparent) 0%, transparent 58%)," +
              "radial-gradient(55% 110% at 100% 0%, color-mix(in oklab, var(--provisional) 5%, transparent) 0%, transparent 56%)",
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
          {/* Down from 1.75/2.125rem, and on the UI sans. A page title is a
              label for where you are, not the headline of the screen; at
              display size in a serif it outweighed the content it introduces,
              which is the opposite of its job. The REPORT's own cover keeps
              both the serif and the scale — that one IS a headline. */}
          <h1 className="font-sans text-[1.3rem] font-semibold leading-[1.2] tracking-[-0.015em] md:text-[1.55rem]">
            {title}
          </h1>
          <p className="m-0 max-w-prose text-[0.82rem] leading-relaxed text-muted-foreground">
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
            opacity: 0.55,
          }}
        />
      </header>
    </div>
  );
}
