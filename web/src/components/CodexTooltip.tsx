import { useState, useCallback, useEffect } from "react";
import { api } from "../lib/api";
import "./furniture.css";

interface CodexEntry {
  code: string;
  title: string;
  domain: string;
  default_severity: string;
}

let _codexCache: Record<string, CodexEntry> | null = null;

function useCodex() {
  const [entries, setEntries] = useState<Record<string, CodexEntry>>(_codexCache ?? {});
  useEffect(() => {
    if (_codexCache) return;
    api.get("/findings/codex")
      .then((data: any) => {
        const map: Record<string, CodexEntry> = {};
        for (const e of data?.entries ?? []) map[e.code] = e;
        _codexCache = map;
        setEntries(map);
      })
      .catch(() => {});
  }, []);
  return entries;
}

interface CodexTooltipProps {
  code: string;
  children?: React.ReactNode;
}

export function CodexTooltip({ code, children }: CodexTooltipProps) {
  const codex = useCodex();
  const [visible, setVisible] = useState(false);
  const entry = codex[code];

  const show = useCallback(() => setVisible(true), []);
  const hide = useCallback(() => setVisible(false), []);

  return (
    <div
      className="codex-trigger"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      tabIndex={0}
      role="button"
      aria-label={`${code} — ${entry?.title ?? "Finding code"}`}
      aria-expanded={visible}
    >
      {children ?? <span className="code-chip">{code}</span>}
      {visible && entry && (
        <div className="codex-tooltip" role="tooltip">
          <div className="ct-code">{code}</div>
          <div className="ct-title">{entry.title}</div>
          <div className="ct-def">{entry.domain?.replace(/_/g, " ")} — {entry.default_severity} severity</div>
        </div>
      )}
    </div>
  );
}
