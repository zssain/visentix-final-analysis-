import { Separator } from "@/components/ui/separator";

/**
 * PageHeader — standard header for every routed screen.
 * Eyebrow = where you are (matches the nav label), title = the screen,
 * description = one plain-language sentence saying what the screen does.
 * `actions` renders on the right: status chips, counts, primary CTA.
 */
interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <>
      <header className="flex flex-wrap items-start justify-between gap-4 pb-5">
        <div className="min-w-0 flex flex-col gap-1">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {eyebrow}
          </div>
          <h1 className="font-display text-2xl font-semibold leading-tight tracking-tight md:text-3xl">
            {title}
          </h1>
          <p className="max-w-prose text-sm text-muted-foreground">{description}</p>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <Separator className="mb-6" />
    </>
  );
}
