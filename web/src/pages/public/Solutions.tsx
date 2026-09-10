import { ClosingNote, PageIntro, SiteLink } from "./shared";
import { AudienceExplorer, ProductGrid } from "./ProductShowcase";
export function Solutions() {
  return <><PageIntro eyebrow="Products & solutions" title={<>Privacy intelligence.<br/><em>Built around your work.</em></>}><p>Four connected products: notice assessment, continuous monitoring, white-label intelligence and quarterly publications.</p><SiteLink to="/pricing">Explore plans & subscriptions</SiteLink></PageIntro><section className="site-wrap products-index"><ProductGrid/></section><AudienceExplorer/><ClosingNote/></>;
}
