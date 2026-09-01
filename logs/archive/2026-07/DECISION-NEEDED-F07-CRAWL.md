# DECISION-NEEDED — F07 corpus growth: public SaaS crawl targets

**Status:** PROPOSED — awaiting in-session approval. **Nothing has been crawled or inserted.** The `open_web` crawler runs ONLY after you approve this list (MUST NOT crawl unapproved domains). On approval I insert these as `crawl_target(status='pending', added_by='F07-corpus')` and run the crawler; each target then records its own honest outcome (`captured/unchanged/no_notice/blocked/consent_wall/error`).

**Why these:** 22 large, public SaaS companies with publicly-published privacy notices — a coherent "SaaS" sector cohort to enrich benchmarks beyond the retail/health/fintech demo set. All are the companies' own public policy pages (no login, no paywall).

| # | domain | sector | notice_url |
|---|---|---|---|
| 1 | slack.com | saas | https://slack.com/trust/privacy/privacy-policy |
| 2 | zoom.us | saas | https://www.zoom.com/en/trust/privacy/privacy-statement/ |
| 3 | notion.so | saas | https://www.notion.so/notion/Privacy-Policy |
| 4 | dropbox.com | saas | https://www.dropbox.com/privacy |
| 5 | atlassian.com | saas | https://www.atlassian.com/legal/privacy-policy |
| 6 | hubspot.com | saas | https://legal.hubspot.com/privacy-policy |
| 7 | salesforce.com | saas | https://www.salesforce.com/company/privacy/ |
| 8 | shopify.com | saas | https://www.shopify.com/legal/privacy |
| 9 | stripe.com | saas | https://stripe.com/privacy |
| 10 | twilio.com | saas | https://www.twilio.com/en-us/legal/privacy |
| 11 | datadoghq.com | saas | https://www.datadoghq.com/legal/privacy/ |
| 12 | snowflake.com | saas | https://www.snowflake.com/privacy-policy/ |
| 13 | asana.com | saas | https://asana.com/terms/privacy-statement |
| 14 | figma.com | saas | https://www.figma.com/legal/privacy/ |
| 15 | zendesk.com | saas | https://www.zendesk.com/company/agreements-and-terms/privacy-notice/ |
| 16 | okta.com | saas | https://www.okta.com/privacy-policy/ |
| 17 | docusign.com | saas | https://www.docusign.com/company/privacy-policy |
| 18 | box.com | saas | https://www.box.com/legal/privacypolicy |
| 19 | mongodb.com | saas | https://www.mongodb.com/legal/privacy-policy |
| 20 | gitlab.com | saas | https://about.gitlab.com/privacy/ |
| 21 | cloudflare.com | saas | https://www.cloudflare.com/privacypolicy/ |
| 22 | intercom.com | saas | https://www.intercom.com/legal/privacy |

**Guardrails on approval:** the crawler re-validates each URL for SSRF at fetch (existing `open_web`/extract defenses); it records honest per-domain status and never fabricates a notice. Freshness lands as a real 2026 capture, so these enter benchmark eligibility only via the normal CQS gate. Licensing note: these are the companies' own public policies (fair-use for benchmarking analysis); flag if legal wants a narrower set.

**To proceed:** reply "approved: crawl" (optionally trim the list) and I'll insert the `crawl_target` rows and run the crawler. **Until then, no crawl.**
