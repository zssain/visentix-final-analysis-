/**
 * F15 — Public Trust Center · UI (public, trust metrics mocked M-27).
 *
 * A no-login page that states what Visentix claims (and doesn't), how customer
 * data is handled, how the intelligence is made reproducible, and that every
 * public statistic is backed by the traceability matrix. Register-appropriate
 * plain language (no security jargon), no legal-verdict vocabulary, honest
 * numbers only.
 */
import { Link } from "react-router-dom";
import { TRUST_METRICS, DATA_COMMITMENTS, LINEAGE_FIELDS } from "./mockData";
import { Card } from "@/components/ui/card";
import { MockBadge } from "@/components/MockBadge";

export function TrustCenter() {
  // AC-3: never render a metric without a source note.
  const metrics = TRUST_METRICS.filter(m => m.sourceNote && m.sourceNote.trim().length > 0);

  return (
    <div className="mx-auto max-w-[1000px]">
      {/* Hero */}
      <div className="mb-8 rounded-xl bg-[linear-gradient(155deg,var(--primary)_0%,color-mix(in_oklab,var(--primary)_78%,var(--verified))_75%,var(--verified)_100%)] px-10 py-11 text-[var(--primary-foreground)] max-md:px-5.5 max-md:py-8">
        <div className="text-[0.72rem] font-bold uppercase tracking-[0.16em] text-[var(--provisional)]">Trust Center</div>
        <h1 className="my-2.5 max-w-[22ch] font-sans text-[clamp(1.8rem,4vw,2.6rem)] font-semibold leading-[1.08] tracking-tight">
          Intelligence you can check, line by line.
        </h1>
        <p className="m-0 max-w-[60ch] text-base leading-relaxed text-[color-mix(in_oklab,var(--primary-foreground)_82%,transparent)]">
          Visentix turns public privacy notices into benchmark intelligence — measured, not asserted. This page
          explains what we claim, how we handle your data, and how every figure we publish traces back to its
          source.
        </p>
      </div>

      {/* Trust metrics strip (M-27).
          This page is PUBLIC, so an unlabelled illustrative figure here is a
          false claim about our own system on the surface whose entire job is
          trust. The badge wording is owner sign-off pending (see F15 / the
          mock tracker); it is shown rather than withheld because unlabelled is
          strictly worse than imperfectly labelled. */}
      <div className="mb-3"><MockBadge id="M-27" /></div>
      <div className="mb-9 grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(180px,1fr))]">
        {metrics.map(m => (
          <div key={m.label} className="rounded-lg border bg-card px-4.5 py-4">
            <div className="font-data text-[1.9rem] font-bold leading-none tabular-nums">{m.value}</div>
            <div className="my-2 text-[0.82rem] font-bold">{m.label}</div>
            <div className="text-[0.74rem] leading-relaxed text-muted-foreground">{m.sourceNote}</div>
          </div>
        ))}
      </div>

      {/* 1 · What we claim */}
      <section className="mb-10">
        <h2 className="mb-1.5 font-sans text-[1.4rem] font-semibold tracking-tight">What we claim — and what we don't</h2>
        <p className="mb-4.5 max-w-[66ch] text-[0.9rem] leading-relaxed text-muted-foreground">
          Visentix answers "compared to whom, with what exposure, at what confidence." It never answers "is this
          legal?" Our reports speak in exposure, maturity, likelihood, benchmark position, and confidence.
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-lg border border-[color-mix(in_oklab,var(--verified)_40%,transparent)] bg-[color-mix(in_oklab,var(--verified)_8%,transparent)] px-5 py-4.5 [&_ul]:m-0 [&_ul]:pl-4.5 [&_li]:mb-1.5 [&_li]:text-[0.84rem] [&_li]:leading-relaxed [&_li]:text-muted-foreground">
            <div className="mb-2.5 flex items-center gap-2 text-[0.9rem] font-bold">We do</div>
            <ul>
              <li>Benchmark a notice against a real cohort of peers.</li>
              <li>Quantify disclosure maturity, exposure likelihood, and transparency.</li>
              <li>Show the confidence behind every figure.</li>
              <li>Point to the specific clause behind every finding.</li>
            </ul>
          </Card>
          <Card className="rounded-lg border bg-muted/40 px-5 py-4.5 [&_ul]:m-0 [&_ul]:pl-4.5 [&_li]:mb-1.5 [&_li]:text-[0.84rem] [&_li]:leading-relaxed [&_li]:text-muted-foreground">
            <div className="mb-2.5 flex items-center gap-2 text-[0.9rem] font-bold">We do not</div>
            <ul>
              <li>Tell you whether a notice is legal or meets a law.</li>
              <li>Issue a determination about your practices.</li>
              <li>Offer legal advice or draft your notice for you.</li>
              <li>Publish a number we cannot trace to its source.</li>
            </ul>
          </Card>
        </div>
      </section>

      {/* 2 · Your data */}
      <section className="mb-10">
        <h2 className="mb-1.5 font-sans text-[1.4rem] font-semibold tracking-tight">Your data</h2>
        <p className="mb-4.5 max-w-[66ch] text-[0.9rem] leading-relaxed text-muted-foreground">
          Trust starts with restraint. Here is exactly what we do — and do not — do with what you send us.
        </p>
        <div className="grid gap-3.5 md:grid-cols-2">
          {DATA_COMMITMENTS.map(c => (
            <div key={c.title} className="rounded-lg border bg-card px-4.5 py-4">
              <div className="mb-1.5 text-[0.9rem] font-bold">{c.title}</div>
              <div className="text-[0.82rem] leading-relaxed text-muted-foreground">{c.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 3 · How the intelligence is made */}
      <section className="mb-10">
        <h2 className="mb-1.5 font-sans text-[1.4rem] font-semibold tracking-tight">How the intelligence is made</h2>
        <p className="mb-4.5 max-w-[66ch] text-[0.9rem] leading-relaxed text-muted-foreground">
          Deterministic formulas, a human expert review gate, and frozen snapshots — the details are public.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link to="/methodology" className="min-w-[200px] flex-1 rounded-md border bg-card px-4 py-3.5 no-underline transition-colors hover:border-ring motion-reduce:transition-none">
            <div className="text-[0.88rem] font-bold">Methodology →</div>
            <div className="mt-0.5 text-[0.78rem] leading-snug text-muted-foreground">The 14 versioned formulas, the review gate, and reproducibility.</div>
          </Link>
          <Link to="/finding-codes" className="min-w-[200px] flex-1 rounded-md border bg-card px-4 py-3.5 no-underline transition-colors hover:border-ring motion-reduce:transition-none">
            <div className="text-[0.88rem] font-bold">Finding Codex →</div>
            <div className="mt-0.5 text-[0.78rem] leading-snug text-muted-foreground">Every finding code with its canonical definition and exposure signal.</div>
          </Link>
          <Link to="/crosswalk" className="min-w-[200px] flex-1 rounded-md border bg-card px-4 py-3.5 no-underline transition-colors hover:border-ring motion-reduce:transition-none">
            <div className="text-[0.88rem] font-bold">Framework Crosswalk →</div>
            <div className="mt-0.5 text-[0.78rem] leading-snug text-muted-foreground">How our domains relate to NIST, ISO 27701, GDPR, and CCPA — descriptively.</div>
          </Link>
        </div>
      </section>

      {/* 4 · Traceability guarantee */}
      <section className="mb-10">
        <h2 className="mb-1.5 font-sans text-[1.4rem] font-semibold tracking-tight">The traceability guarantee</h2>
        <p className="mb-4.5 max-w-[66ch] text-[0.9rem] leading-relaxed text-muted-foreground">
          No score exists without its lineage. Every derived value stores four things, and every report
          regenerates identically from the snapshot it was frozen into.
        </p>
        <div className="overflow-hidden rounded-lg border">
          {LINEAGE_FIELDS.map(f => (
            <div key={f.field} className="flex items-baseline gap-3.5 border-b px-4 py-3 last:border-b-0 max-md:flex-col max-md:gap-1.5">
              <span className="min-w-[132px] shrink-0 whitespace-nowrap rounded-sm bg-primary px-2.5 py-1 text-center font-data text-[0.78rem] font-bold text-primary-foreground">{f.field}</span>
              <span className="text-[0.84rem] leading-snug text-muted-foreground">{f.desc}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
