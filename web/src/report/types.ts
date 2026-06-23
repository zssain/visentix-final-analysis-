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
}
