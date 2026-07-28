import { PageHeader } from "../../components/PageHeader";
import "../../components/furniture.css";

export type LegalSection = { heading: string; body: string[] };

/**
 * Shared renderer for the public /privacy and /terms documents. Plain-language,
 * no auth, included in the Cloudflare Pages build. Content lives in the two
 * page modules that call this; this component only lays it out.
 */
export function LegalPage({
  eyebrow, title, effectiveDate, intro, sections,
}: {
  eyebrow: string;
  title: string;
  effectiveDate: string;
  intro: string;
  sections: LegalSection[];
}) {
  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      <PageHeader eyebrow={eyebrow} title={title} description={intro} />
      <p style={{ color: "var(--text-muted)", fontSize: "0.82rem", marginTop: -8, marginBottom: 32 }}>
        Effective date: <strong>{effectiveDate}</strong>
      </p>
      {sections.map((s, i) => (
        <section key={i} style={{ marginBottom: 32 }}>
          <h2 style={{
            fontFamily: "var(--font-display)", fontSize: "1.25rem", fontWeight: 700,
            color: "var(--navy)", letterSpacing: "-0.02em", marginBottom: 10,
          }}>
            {s.heading}
          </h2>
          {s.body.map((p, j) => (
            <p key={j} style={{ color: "var(--text-secondary)", fontSize: "0.92rem", lineHeight: 1.6, marginBottom: 10 }}>
              {p}
            </p>
          ))}
        </section>
      ))}
      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: 40, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
        Questions about this document? Email <a href="mailto:privacy@visentix.ai">privacy@visentix.ai</a>.
      </p>
    </div>
  );
}
