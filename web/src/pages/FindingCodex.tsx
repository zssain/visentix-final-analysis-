/**
 * Finding Codex — real data from GET /findings/codex
 * No mock data. Fetches the finding_type catalog from Supabase.
 */
import { useState, useMemo, useEffect } from "react";
import { api } from "../lib/api";
import { PageHeader } from "../components/PageHeader";
import { ChevronDown, Search } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Severity is a STANDING, so it uses the traffic-light scale (OD-13).
 *  An unrecognised severity gets a neutral pill rather than a guessed colour. */
function severityVariant(sev: string) {
  const s = sev?.toLowerCase();
  if (s === "high" || s === "critical") return "standing-bad" as const;
  if (s === "medium" || s === "elevated" || s === "moderate") return "standing-mid" as const;
  if (s === "low") return "standing-good" as const;
  return "secondary" as const;
}

const DOMAINS = [
  "data_sharing", "tracking_cookies", "consumer_rights",
  "cross_border", "sensitive_data", "retention",
  "children_teens", "ai_automated_decisions", "other",
] as const;
type Domain = typeof DOMAINS[number];

function domainLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

interface CodexEntry {
  code: string;
  domain: string;
  title: string;
  default_severity: string;
  sme_authored: boolean;
  regulator_relevance: Record<string, number>;
  recommendations: { title: string; body_template: string; severity_bucket: string }[];
  legal_references: { framework: string; citation: string; title: string; summary: string; official_url: string; is_primary: boolean }[];
}

export function FindingCodex() {
  const [entries, setEntries] = useState<CodexEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDomain, setActiveDomain] = useState<Domain | "all">("all");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get("/findings/codex")
      .then((data: { entries: CodexEntry[] }) => setEntries(data.entries || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() =>
    entries.filter(e =>
      (activeDomain === "all" || e.domain === activeDomain) &&
      (search === "" || e.code.toLowerCase().includes(search.toLowerCase()) ||
       e.title.toLowerCase().includes(search.toLowerCase()))
    ),
  [entries, activeDomain, search]);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Finding Codes"
        title="Finding Code Definitions"
        description={`Definitions for all ${entries.length} finding codes from the database catalog — what each code means, the exposure it signals, and linked legal references.`}
      />

      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        {/* Domain filter */}
        <Card className="self-start p-4 md:sticky md:top-6">
          <div className="mb-3 text-sm font-semibold">Filter by domain</div>
          <nav className="flex flex-col gap-0.5">
            <button
              onClick={() => setActiveDomain("all")}
              aria-pressed={activeDomain === "all"}
              className={cn(
                "rounded-md px-3 py-1.5 text-left text-sm transition-colors",
                activeDomain === "all"
                  ? "bg-accent font-semibold text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
              )}
            >
              All domains
            </button>
            {DOMAINS.map(d => (
              <button
                key={d}
                onClick={() => setActiveDomain(activeDomain === d ? "all" : d)}
                aria-pressed={activeDomain === d}
                className={cn(
                  "rounded-md px-3 py-1.5 text-left text-sm transition-colors",
                  activeDomain === d
                    ? "bg-accent font-semibold text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                )}
              >
                {domainLabel(d)}
              </button>
            ))}
          </nav>
        </Card>

        {/* Entries */}
        <div className="min-w-0">
          <div className="relative mb-4">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder={`Search ${filtered.length} finding codes...`}
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9"
              aria-label="Search finding codes"
            />
          </div>

          {loading ? (
            <div className="flex flex-col gap-2">
              {[0,1,2,3].map(i => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : filtered.length === 0 ? (
            <Card className="items-center py-12 text-center text-sm text-muted-foreground">
              No finding codes match this filter.
            </Card>
          ) : (
            <div className="flex flex-col gap-2">
              {filtered.map(e => {
                const isOpen = expanded === e.code;
                return (
                  <Card key={e.code} className="gap-0 overflow-hidden py-0">
                    <button
                      onClick={() => setExpanded(isOpen ? null : e.code)}
                      aria-expanded={isOpen}
                      className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-accent/50"
                    >
                      <Badge className="font-data shrink-0">{e.code}</Badge>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold">{e.title}</div>
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                          {domainLabel(e.domain)}
                        </div>
                      </div>
                      <ChevronDown
                        className={cn(
                          "size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
                          isOpen && "rotate-180"
                        )}
                        aria-hidden="true"
                      />
                    </button>

                    {isOpen && (
                      <div className="flex flex-col gap-4 border-t px-4 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                            Severity
                          </span>
                          <Badge variant={severityVariant(e.default_severity)} className="uppercase">
                            {e.default_severity}
                          </Badge>
                          {!e.sme_authored && (
                            <span className="text-xs text-muted-foreground">(Pending SME review)</span>
                          )}
                        </div>

                        {Object.keys(e.regulator_relevance).length > 0 && (
                          <div>
                            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Regulator Relevance
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {Object.entries(e.regulator_relevance).map(([reg, weight]) => (
                                <Badge key={reg} variant="outline" className="font-data">
                                  {reg}: {(weight as number).toFixed(1)}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {e.legal_references.length > 0 && (
                          <div>
                            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Legal References
                            </div>
                            <ul className="flex flex-col gap-2">
                              {e.legal_references.map((lr, i) => (
                                <li key={i} className="text-sm">
                                  <span className="font-semibold">{lr.framework}</span>
                                  {" · "}
                                  <span className="text-muted-foreground">{lr.citation}</span>
                                  {lr.is_primary && <Badge className="ml-1.5 text-[10px]">PRIMARY</Badge>}
                                  {lr.official_url && (
                                    <a
                                      href={lr.official_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="ml-2 text-xs underline underline-offset-4 hover:text-foreground"
                                    >
                                      Official source ↗
                                    </a>
                                  )}
                                  {lr.summary && (
                                    <p className="mt-0.5 text-xs text-muted-foreground">{lr.summary}</p>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {e.recommendations.length > 0 && (
                          <div>
                            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Recommendation
                            </div>
                            <p className="max-w-prose text-sm text-muted-foreground">
                              {e.recommendations[0].body_template?.replace(/\{[^}]+\}/g, "[...]") ?? "See report."}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
