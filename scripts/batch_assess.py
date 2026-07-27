"""Batch-assess company privacy policies to build benchmark population.

Runs against the deployed API (or local). Skips companies already assessed.
Polite: 5s delay between assessments to avoid overwhelming the LLM.

Usage:
    # Against deployed API (RunPod must be running for LLM classification):
    PYTHONPATH=. python scripts/batch_assess.py --api https://visentix-api.salmoncoast-f5a3917f.eastus.azurecontainerapps.io

    # Against local API:
    PYTHONPATH=. python scripts/batch_assess.py --api http://localhost:8000

    # Dry run (just list URLs, don't submit):
    PYTHONPATH=. python scripts/batch_assess.py --dry-run
"""

import argparse
import json
import logging
import time

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("batch_assess")

# ── Company privacy policy URLs ──────────────────────────────
# Direct /privacy URLs where possible (skips discovery, faster + more reliable)

COMPANIES = [
    # Tech — Large
    ("Apple", "https://www.apple.com/legal/privacy/en-ww/"),
    ("Microsoft", "https://privacy.microsoft.com/en-us/privacystatement"),
    ("Google", "https://policies.google.com/privacy"),
    ("Amazon", "https://www.amazon.com/gp/help/customer/display.html?nodeId=468496"),
    ("Meta", "https://www.facebook.com/privacy/policy/"),
    ("Netflix", "https://help.netflix.com/legal/privacy"),
    ("Spotify", "https://www.spotify.com/legal/privacy-policy/"),
    ("Zoom", "https://explore.zoom.us/en/privacy/"),
    ("Slack", "https://slack.com/trust/privacy/privacy-policy"),
    ("Dropbox", "https://www.dropbox.com/privacy"),
    ("Twitter/X", "https://twitter.com/en/privacy"),
    ("LinkedIn", "https://www.linkedin.com/legal/privacy-policy"),
    ("TikTok", "https://www.tiktok.com/legal/privacy-policy"),
    ("Snap", "https://values.snap.com/privacy/privacy-policy"),
    ("Pinterest", "https://policy.pinterest.com/en/privacy-policy"),
    ("Reddit", "https://www.reddit.com/policies/privacy-policy"),

    # Tech — Mid
    ("Stripe", "https://stripe.com/privacy"),
    ("Shopify", "https://www.shopify.com/legal/privacy"),
    ("Twilio", "https://www.twilio.com/legal/privacy"),
    ("HubSpot", "https://legal.hubspot.com/privacy-policy"),
    ("Zendesk", "https://www.zendesk.com/company/agreements-and-terms/privacy-policy/"),
    ("Atlassian", "https://www.atlassian.com/legal/privacy-policy"),
    ("Notion", "https://www.notion.so/Privacy-Policy-3468d120cf614d4c9014c09f6adc9091"),
    ("Canva", "https://www.canva.com/policies/privacy-policy/"),
    ("Figma", "https://www.figma.com/legal/privacy/"),
    ("GitHub", "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"),

    # Finance
    ("JPMorgan Chase", "https://www.chase.com/digital/resources/privacy-security/privacy/online-privacy-policy"),
    ("PayPal", "https://www.paypal.com/us/legalhub/privacy-full"),
    ("Robinhood", "https://robinhood.com/us/en/about/legal/"),
    ("Coinbase", "https://www.coinbase.com/legal/privacy"),
    ("Square/Block", "https://squareup.com/us/en/legal/general/privacy"),
    ("Venmo", "https://venmo.com/legal/us-privacy-policy/"),
    ("Wise", "https://wise.com/us/legal/global-privacy-statement-for-wise-personal"),
    ("Plaid", "https://plaid.com/legal/#consumers"),

    # Health
    ("UnitedHealth", "https://www.uhc.com/privacy"),
    ("CVS Health", "https://www.cvs.com/help/privacy-policy"),
    ("Teladoc", "https://www.teladoc.com/privacy-policy/"),
    ("GoodRx", "https://www.goodrx.com/privacy-policy"),

    # Retail
    ("Walmart", "https://corporate.walmart.com/privacy-security/walmart-privacy-policy"),
    ("Target", "https://www.target.com/c/target-privacy-policy/-/N-4sr7p"),
    ("Nike", "https://agreementservice.svs.nike.com/us/en_us/rest/agreement?agreementType=privacyPolicy&country=US&language=en&requestType=redirect"),
    ("Starbucks", "https://www.starbucks.com/terms/privacy-policy/"),
    ("Costco", "https://www.costco.com/privacy-policy.html"),
    ("Best Buy", "https://www.bestbuy.com/site/help-topics/privacy-policy/pcmcat204400050062.c"),
    ("Home Depot", "https://www.homedepot.com/privacy/privacy-and-security-statement"),
    ("Etsy", "https://www.etsy.com/legal/privacy/"),

    # Education
    ("Coursera", "https://www.coursera.org/about/privacy"),
    ("Udemy", "https://www.udemy.com/terms/privacy/"),
    ("Khan Academy", "https://www.khanacademy.org/about/privacy-policy"),
    ("Duolingo", "https://www.duolingo.com/privacy"),
    ("Chegg", "https://www.chegg.com/privacypolicy"),

    # Telecom
    ("Verizon", "https://www.verizon.com/about/privacy/full-privacy-policy"),
    ("AT&T", "https://about.att.com/csr/home/privacy.html"),
    ("T-Mobile", "https://www.t-mobile.com/privacy-center/our-practices/privacy-policy"),
    ("Comcast", "https://www.xfinity.com/privacy/policy"),

    # Travel & Transport
    ("Airbnb", "https://www.airbnb.com/terms/privacy_policy"),
    ("Uber", "https://www.uber.com/legal/en/document/?name=privacy-notice"),
    ("Lyft", "https://www.lyft.com/privacy"),
    ("Expedia", "https://www.expedia.com/lp/lg-privacypolicy"),
    ("Booking.com", "https://www.booking.com/content/privacy.en-us.html"),
    ("DoorDash", "https://www.doordash.com/consumer-privacy"),

    # Insurance
    ("Geico", "https://www.geico.com/privacy/"),
    ("Progressive", "https://www.progressive.com/privacy/"),
    ("State Farm", "https://www.statefarm.com/customer-care/privacy-security/privacy"),
    ("Allstate", "https://www.allstate.com/privacy"),

    # Media & Entertainment
    ("Disney", "https://privacy.thewaltdisneycompany.com/en/current-privacy-policy/"),
    ("Hulu", "https://www.hulu.com/privacy"),
    ("Twitch", "https://www.twitch.tv/p/legal/privacy-notice/"),
    ("Roku", "https://www.roku.com/en-us/legal/privacy-policy"),

    # SaaS / Enterprise
    ("Salesforce", "https://www.salesforce.com/company/privacy/"),
    ("Oracle", "https://www.oracle.com/legal/privacy/"),
    ("SAP", "https://www.sap.com/about/legal/privacy.html"),
    ("ServiceNow", "https://www.servicenow.com/privacy-statement.html"),
    ("Workday", "https://www.workday.com/en-us/privacy.html"),

    # Cloud / Infrastructure
    ("Cloudflare", "https://www.cloudflare.com/privacypolicy/"),
    ("DigitalOcean", "https://www.digitalocean.com/legal/privacy-policy"),
    ("MongoDB", "https://www.mongodb.com/legal/privacy-policy"),
    ("Datadog", "https://www.datadoghq.com/legal/privacy/"),

    # Social / Communication
    ("Discord", "https://discord.com/privacy"),
    ("Telegram", "https://telegram.org/privacy"),
    ("Signal", "https://signal.org/legal/#privacy-policy"),
    ("WhatsApp", "https://www.whatsapp.com/legal/privacy-policy"),
]


def login(api_base: str, email: str, password: str) -> str:
    """Login and return JWT token."""
    r = httpx.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def assess(api_base: str, token: str, url: str) -> dict:
    """Submit a URL for assessment. Returns the response dict."""
    r = httpx.post(
        f"{api_base}/assessments/",
        headers={"Authorization": f"Bearer {token}"},
        data={"url": url},
        timeout=600,  # 10 min — LLM classification can be slow
    )
    return {"status_code": r.status_code, "body": r.json() if r.status_code < 500 else r.text[:200]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Just list URLs")
    parser.add_argument("--email", default="admin@visentix.com")
    parser.add_argument("--password", default="VisentixDemo2026!")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between assessments")
    parser.add_argument("--start", type=int, default=0, help="Start from company index N")
    parser.add_argument("--limit", type=int, default=0, help="Max companies to process (0=all)")
    args = parser.parse_args()

    if args.dry_run:
        for i, (name, url) in enumerate(COMPANIES):
            print(f"  {i:3d}. {name:20s} {url}")
        print(f"\nTotal: {len(COMPANIES)} companies")
        return

    token = login(args.api, args.email, args.password)
    log.info("Logged in to %s", args.api)

    companies = COMPANIES[args.start:]
    if args.limit > 0:
        companies = companies[:args.limit]

    results = {"success": 0, "failed": 0, "skipped": 0}

    for i, (name, url) in enumerate(companies):
        idx = i + args.start
        log.info("[%d/%d] %s — %s", idx + 1, len(COMPANIES), name, url[:60])

        try:
            result = assess(args.api, token, url)
            code = result["status_code"]

            if code == 201:
                body = result["body"]
                score = body.get("scores", {}).get("overall_intelligence", "?")
                clauses = body.get("clauses", 0)
                findings = body.get("scores", {}).get("finding_count", 0)
                log.info("  OK: score=%.1f clauses=%d findings=%d", float(score), clauses, findings)
                results["success"] += 1
            elif code == 422:
                log.warning("  SKIP (422): %s", result["body"].get("detail", "")[:100])
                results["skipped"] += 1
            else:
                log.error("  FAIL (%d): %s", code, str(result["body"])[:100])
                results["failed"] += 1

        except Exception as e:
            log.error("  ERROR: %s", e)
            results["failed"] += 1

        if i < len(companies) - 1:
            time.sleep(args.delay)

    print(f"\n{'='*60}")
    print(f"  Success:  {results['success']}")
    print(f"  Skipped:  {results['skipped']}")
    print(f"  Failed:   {results['failed']}")
    print(f"  Total:    {sum(results.values())}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
