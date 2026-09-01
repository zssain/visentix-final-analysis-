/**
 * PageHeader — standard header for every routed screen.
 *
 * Eyebrow = where you are (matches the nav label), title = the screen,
 * description = one plain-language sentence saying what the screen does.
 * `actions` renders on the right: status chips, counts, primary CTA.
 *
 * PRESENTATION (2026-09-01). It was three stacked text blocks and a plain grey
 * rule — identical on all thirteen screens that use it, and carrying none of
 * the language the rest of the product now speaks. It is now a panel: a quiet
 * brand wash, the eyebrow led by a teal mark that ties it to the selected nav
 * item, and a rule that fades teal into gold instead of stopping dead.
 *
 * All of it is decorative and `aria-hidden`; the words, the heading level and
 * the reading order are unchanged, so nothing here alters what the screen says
 * or how it is announced.
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
      <header className="relative flex flex-wrap items-start justify-between gap-x-6 gap-y-4 overflow-hidden rounded-2xl border px-6 py-6 md:px-7 md:py-7">
        {/* Wash. Anchored top-left behind the title so it reads as light falling
            on the panel rather than a tinted box. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10"
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
          <h1 className="font-display text-2xl font-semibold leading-tight tracking-tight md:text-[2rem]">
            {title}
          </h1>
          <p className="m-0 max-w-prose text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        </div>

        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </header>

      {/* A rule that starts in the brand and fades out, rather than a grey line
          drawn edge to edge. Decorative: the panel border above already does the
          structural separating. */}
      <div
        aria-hidden="true"
        className="mt-px h-px w-full"
        style={{
          background:
            "linear-gradient(90deg, var(--verified) 0%, var(--provisional) 22%, transparent 70%)",
          opacity: 0.5,
        }}
      />
    </div>
  );
}
