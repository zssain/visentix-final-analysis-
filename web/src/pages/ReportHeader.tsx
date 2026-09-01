/**
 * ReportHeader — the bar above a report.
 *
 * It was a bare row: a "← Back to Assessments" link and a Download button on
 * blank page. That told a reader nothing about what they had opened — no title,
 * no organisation, no indication of whether the thing below was a draft — and
 * it scrolled away immediately, so on a twelve-part document the way back and
 * the download were only reachable from the top.
 *
 * Now: a breadcrumb that says where this sits, the organisation as the title
 * (the report is *about* them, so their name is the heading), the draft state
 * where it cannot be missed, and the actions — all pinned.
 *
 * It is deliberately NOT the shadcn `PageHeader`. That component is the header
 * of a *screen* and always renders an `<h1>`; the report below already opens
 * with its own cover and title, and two `<h1>`s on one page is a worse outcome
 * than a slightly different-looking bar. This is chrome around a document, so
 * it uses the same glass recipe and a `<p>` for the name.
 */
import { Link } from "react-router-dom";
import { ChevronRight, Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ReportHeaderProps {
  organization: string;
  /** Frozen/generated date as stored — shown verbatim, never reformatted into a guess. */
  generatedDate?: string;
  isDraft: boolean;
  onDownload: () => void;
  downloading: boolean;
  downloadError: string | null;
}

export function ReportHeader({
  organization, generatedDate, isDraft, onDownload, downloading, downloadError,
}: ReportHeaderProps) {
  return (
    <div
      className="sticky top-[calc(3.5rem+0.75rem)] md:top-3 z-30 mb-6 print:static print:mb-4"
      data-testid="report-header"
    >
      <div className="relative overflow-hidden rounded-2xl border shadow-lg backdrop-blur-xl bg-card supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--card)_72%,transparent)] print:border print:bg-card print:shadow-none print:backdrop-blur-none">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-5 py-3.5 md:px-6">
          <div className="flex min-w-0 flex-col gap-1">
            {/* Breadcrumb. `/assessments`, never `/` — "/" is the ROLE-BASED
                home, so an admin would land on the Console and an SME on the
                Workbench while the crumb said Assessments. */}
            <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
              <Link
                to="/assessments"
                className="rounded-sm px-1 py-0.5 font-medium hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
              >
                Assessments
              </Link>
              <ChevronRight className="size-3 shrink-0 opacity-60" aria-hidden="true" />
              <span aria-current="page" className="truncate px-1 py-0.5 text-foreground">
                Report
              </span>
            </nav>

            <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              {/* The organisation is the heading — the report is about them.
                  Not an <h1>: the report's own cover carries that, and two
                  first-level headings on one page is worse than a bar that
                  reads slightly differently from a screen header. */}
              <p className="m-0 min-w-0 truncate font-display text-lg font-semibold leading-tight tracking-[-0.01em]">
                {organization}
              </p>
              {/* Draft state where it cannot be missed. The report carries its
                  own watermark and ribbon, but a reader who scrolls straight to
                  a finding should not have to scroll back to learn it is
                  unreviewed. */}
              {isDraft && <Badge variant="provisional">Draft — pending review</Badge>}
              {generatedDate && (
                <span className="font-data text-xs tabular-nums text-muted-foreground">
                  {generatedDate}
                </span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2 print:hidden">
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={onDownload}
              disabled={downloading}
            >
              <Download aria-hidden="true" />
              {downloading ? "Downloading…" : "Download PDF"}
            </Button>
          </div>
        </div>

        {/* The error gets its own row rather than sitting inline beside the
            button, where a long message pushed the layout around. */}
        {downloadError && (
          <p
            role="alert"
            className="m-0 border-t bg-[color-mix(in_oklab,var(--standing-bad)_8%,transparent)] px-5 py-2 text-sm text-[var(--standing-bad)] md:px-6"
          >
            {downloadError}
          </p>
        )}

        {/* Brand hairline, clipped to the panel's own curve — the same treatment
            as the page header and the sidebar. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, var(--verified) 0%, var(--provisional) 26%, transparent 72%)",
            opacity: 0.7,
          }}
        />
      </div>
    </div>
  );
}
