/**
 * F14 — Notice Rewrite Prompts (Trust Language Studio) · UI (mocks, M-26).
 *
 * For each disclosure gap, show a benchmark-informed LANGUAGE PATTERN beside the
 * org's current wording, so their trust/marketing team can improve clarity.
 * Patterns are examples of how clearer peer notices read — never legal drafting,
 * obligation, or verdict (F14 guardrails). UI-only ahead of the pattern library.
 */
import { useState } from "react";
import { PageHeader } from "../../components/PageHeader";
import { IntelligenceMark } from "../../components/IntelligenceMark";
import { FlashNotice } from "../../components/FlashNotice";
import { useFlash } from "../../lib/useFlash";
import { LOW_CONFIDENCE_COHORT_N } from "../../lib/scoreBands";
import { PROMPTS, type GapStatus } from "./mockData";
import "../../components/furniture.css";
import "./rewrite.css";

const STATUS_LABEL: Record<GapStatus, string> = {
  missing: "Not addressed",
  could_be_clearer: "Could be clearer",
  adequate: "Reads clearly",
};

export function NoticeRewrite() {
  const [done, setDone] = useState<Set<string>>(new Set());
  const [flash, showFlash] = useFlash();

  const toggleDone = (id: string) =>
    setDone(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });

  // Only claim success when the copy actually succeeded — honest feedback.
  const copyPattern = (text: string) => {
    if (!navigator.clipboard) {
      showFlash("Copying isn't available here — select the text and copy it manually.");
      return;
    }
    navigator.clipboard.writeText(text).then(
      () => showFlash("Language pattern copied — adapt it to your own voice."),
      () => showFlash("Couldn't copy automatically — select the text and copy it manually."),
    );
  };

  // "Addressed" = adequate domains + any prompt the user has checked off.
  const addressed = PROMPTS.filter(p => p.status === "adequate" || done.has(p.domainId)).length;
  const total = PROMPTS.length;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto" }}>
      <PageHeader
        eyebrow="Rewrite"
        title="Trust Language Studio"
        description="For each disclosure gap in your notice, see how the clearest peer notices phrase it. These are language patterns to adapt — not legal drafting."
        actions={<IntelligenceMark />}
      />

      {/* Guardrail banner (AC-5) */}
      <div className="guardrail-banner">
        <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>ⓘ</span>
        <span>
          <b>Language patterns, not legal drafting.</b> Each suggestion shows how clearer notices in your peer
          cohort tend to read. Adapt it to your own voice and facts — Visentix does not tell you what your notice
          has to say, and these are not legal advice.
        </span>
      </div>

      <FlashNotice message={flash} />

      {/* Progress (AC-6) */}
      <div className="rw-progress">
        <span className="rw-progress-count">{addressed} / {total} domains reading clearly</span>
        <span className="rw-progress-bar"><span style={{ width: `${(addressed / total) * 100}%` }} /></span>
      </div>

      {PROMPTS.map(p => {
        const isDone = done.has(p.domainId);
        const isAdequate = p.status === "adequate";
        const lowConf = p.cohortN < LOW_CONFIDENCE_COHORT_N;
        return (
          <div key={p.domainId} className={`rw-card ${isAdequate ? "adequate" : ""} ${isDone ? "done" : ""}`}>
            <div className="rw-card-head">
              <span className="domain-chip">{p.domainId}</span>
              <span className="rw-domain-name">{p.domainName}</span>
              <span className={`rw-status ${p.status}`}>{STATUS_LABEL[p.status]}</span>
              {!isAdequate && (
                <label className="rw-check">
                  <input type="checkbox" checked={isDone} onChange={() => toggleDone(p.domainId)} />
                  Handled
                </label>
              )}
            </div>

            {/* Adequate domains stay compact — celebrate what already reads well. */}
            {isAdequate ? (
              <div style={{ padding: "0 18px 14px 18px" }}>
                <div className="rw-current">“{p.currentExcerpt}”</div>
                <div className="rw-rationale">{p.rationale}</div>
              </div>
            ) : (
              <div className="rw-body">
                {/* Current state — always shown beside the suggestion (AC-1) */}
                <div>
                  <div className="rw-col-label">Your notice today</div>
                  {p.currentExcerpt ? (
                    <div className="rw-current">“{p.currentExcerpt}”</div>
                  ) : (
                    <div className="rw-current absent">This domain is not addressed in your notice.</div>
                  )}
                </div>

                {/* Suggested pattern */}
                <div>
                  <div className="rw-col-label">A clearer pattern from your cohort</div>
                  <div className="rw-pattern">“{p.pattern}”</div>
                  <div className="rw-rationale">{p.rationale}</div>
                  <div className="rw-source">
                    <span>Drawn from n={p.cohortN} top-quartile notices · de-identified</span>
                    {lowConf && <span className="rw-lowconf">· small cohort — interpret with caution</span>}
                    <button className="rw-copy" onClick={() => copyPattern(p.pattern)}>Copy pattern</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
