/** Report payload types — matches the backend ReportPayload exactly. */

export interface ReportSection {
  number: number;
  title: string;
  content: Record<string, unknown>;
}

export interface ReportPayload {
  assessment_id: string;
  organization_name: string;
  generated_date: string;
  sections: ReportSection[];
  cohort_size: number;
  cohort_date: string;
  vci_label: string;
  draft_banner?: string;
  /* M-09: authoritative snapshot provenance, injected by the backend from the
     stored report_snapshot row (id + frozen-at) — takes precedence over any
     value baked into a section at assembly time. */
  _snapshot_id?: string;
  _generated_at?: string;
  _content_hash?: string;
  _report_version?: number;
}
