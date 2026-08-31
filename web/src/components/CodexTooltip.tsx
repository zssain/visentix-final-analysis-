import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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
      .then((data) => {
        const map: Record<string, CodexEntry> = {};
        const entries = (data as { entries?: CodexEntry[] } | null)?.entries ?? [];
        for (const e of entries) map[e.code] = e;
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
  const entry = codex[code];

  const trigger = children ?? (
    <Badge variant="outline" className="font-data cursor-help">{code}</Badge>
  );

  // No entry loaded yet (or unknown code): render the chip plainly rather than
  // a tooltip that opens onto nothing.
  if (!entry) return <span>{trigger}</span>;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} aria-label={`${code} — ${entry.title}`}>{trigger}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <div className="font-data text-[11px] font-bold tracking-wide">{code}</div>
        <div className="font-semibold">{entry.title}</div>
        <div className="opacity-80 capitalize">
          {entry.domain?.replace(/_/g, " ")} — {entry.default_severity} severity
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
