/** Governed clause-taxonomy labels used by customer-facing report sections. */
const DOMAIN_LABELS: Record<string, string> = {
  ai_automated_decisions: "AI & Automated Decisions",
  children_teens: "Children & Teens",
  consumer_rights: "Consumer Rights",
  cross_border: "Cross-Border Transfers",
  data_sharing: "Data Sharing",
  retention: "Retention",
  sensitive_data: "Sensitive Data",
  tracking_cookies: "Tracking & Cookies",
};

/** Unknown values remain visibly raw; the UI never guesses a taxonomy label. */
export function domainLabel(slug: string): string {
  return DOMAIN_LABELS[slug] ?? slug;
}
