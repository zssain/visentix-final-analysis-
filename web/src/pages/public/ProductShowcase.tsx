import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "radix-ui";
import { Activity, ArrowRight, ArrowUpRight, BookOpen, Check, FileText, Layers, ScanLine, Search, SlidersHorizontal, Users } from "lucide-react";
import { productCatalog, type ProductId } from "./products";
import { Eyebrow, Reveal, SiteLink } from "./shared";

const productTones = { sage: "tone-sage", sky: "tone-sky", peach: "tone-peach", lilac: "tone-lilac" };
const icons = { assessment: FileText, monitoring: Activity, partner: Users, quarterly: BookOpen };

export function ProductVisual({ kind }: { kind: ProductId }) {
  return <div className={`product-visual visual-${kind}`} aria-hidden="true">
    {kind === "assessment" && <><div className="visual-report"><span>VISENTIX / INTELLIGENCE</span><strong>Privacy notice<br />assessment.</strong><div className="visual-lines"><i /><i /><i /></div><div className="visual-report-bottom"><span>Evidence<br />Context<br />Confidence</span><ScanLine size={36} strokeWidth={1} /></div></div><div className="visual-orbit" /></>}
    {kind === "monitoring" && <><div className="visual-radar"><i /><i /><i /><span /></div><div className="visual-caption">DISCLOSURE → CHANGE → CONTEXT</div></>}
    {kind === "partner" && <><div className="visual-client back"><Layers size={22} /><span>CLIENT WORKSPACE</span><strong>Your client.<br />Your perspective.</strong></div><div className="visual-client front"><span>YOUR BRAND</span><strong>Intelligence<br />that travels.</strong><ArrowUpRight size={27} /></div></>}
    {kind === "quarterly" && <><div className="visual-journal"><span>VISENTIX / PUBLICATIONS</span><strong>Privacy<br />intelligence.<br /><em>The wider view.</em></strong><div /><small>DISCLOSURE · BENCHMARKS · EVIDENCE</small></div></>}
  </div>;
}

export function ProductGrid() {
  return <div className="product-grid">{productCatalog.map(p => <Reveal key={p.id}><article className={`product-card ${productTones[p.tone]}`}><Link to={p.path} className="product-art-link" aria-label={`Explore ${p.short}`}><ProductVisual kind={p.id} /><ArrowUpRight size={20} /></Link><div className="product-card-copy"><span className="site-kicker">{p.category}</span><h3><Link to={p.path}>{p.short}</Link></h3><p>{p.description}</p><ul>{p.features.map(f=><li key={f}><Check size={13} />{f}</li>)}</ul><SiteLink to={p.path} subtle>Explore product</SiteLink></div></article></Reveal>)}</div>;
}

const sections = ["Executive overview", "Disclosure domains", "Benchmark context", "Findings & evidence"];
const reportText = [
  ["The assessment, at a glance.", "An executive reading of the notice, its benchmark context and the findings that deserve attention.", ["Assessment scope", "Headline intelligence", "Review status"]],
  ["A structured view of disclosure.", "Explore assessed themes such as retention, data sharing, consumer rights and AI-related disclosure.", ["Disclosure maturity", "Domain-level evidence", "Confidence in context"]],
  ["Compared to whom?", "Understand a benchmark through its eligible peer population, as-of date and the strength of the supporting evidence.", ["Peer population", "Benchmark position", "Confidence and limitations"]],
  ["Follow the reasoning.", "Trace findings to source clauses and recorded references, with the formula version and review status alongside them.", ["Source references", "Finding definitions", "Formula lineage"]],
];

export function WorkspaceTour({ kind = "assessment", compact = false }: { kind?: ProductId; compact?: boolean }) {
  const [section, setSection] = useState(0);
  const contentId = useId();
  const item = productCatalog.find(p => p.id === kind)!;
  return <div className={`workspace-tour ${compact ? "tour-compact" : ""}`}>
    <div className="tour-chrome"><span className="tour-brand">v.</span><span>Visentix / {item.short}</span><span className="tour-label">Product walkthrough</span></div>
    <div className="tour-body"><aside className="tour-sidebar"><span className="site-kicker">EXPLORE THE PRODUCT</span>{(kind === "assessment" ? sections : ["Overview", "What it delivers", "How it connects"]).map((name,i)=><button key={name} type="button" aria-pressed={section===i} aria-controls={contentId} onClick={()=>setSection(i)}><span>{String(i+1).padStart(2,"0")}</span>{name}<ArrowRight size={12}/></button>)}<div className="tour-sidebar-foot"><Layers size={15}/><span>One intelligence engine</span></div></aside>
      <div className="tour-content" id={contentId}><div className="tour-content-toolbar"><span>{kind === "assessment" ? "REPORT EXPLORER" : item.category}</span><SlidersHorizontal size={15}/></div>
        {kind === "assessment" ? <><div className="tour-content-title"><FileText size={19}/><span>Privacy Notice Assessment</span></div><h3>{reportText[section][0]}</h3><p>{reportText[section][1]}</p><div className="tour-evidence-grid">{(reportText[section][2] as string[]).map((label,i)=><div key={label}><span className="tour-node">{i===0?<FileText size={16}/>:i===1?<Search size={16}/>:<Layers size={16}/>}</span><strong>{label}</strong><span>Included in the report structure</span></div>)}</div><div className="tour-evidence-footer"><span>NOTICE</span><i/><span>PEER CONTEXT</span><i/><span>INTELLIGENCE</span></div></> : <><div className="tour-content-title">{(()=>{const Icon=icons[kind];return <Icon size={19}/>;})()}<span>{item.short}</span></div><h3>{section===0 ? item.title : section===1 ? "Built around your workflow." : "Connected by the evidence."}</h3><p>{section===0? item.description : section===1 ? `For ${item.audience.toLowerCase()}.` : "The same assessment evidence supports reports, monitoring, partner delivery and approved publications."}</p><div className="tour-feature-stack">{item.features.map((feature,i)=><div key={feature}><span>0{i+1}</span><strong>{feature}</strong><ArrowUpRight size={17}/></div>)}</div><div className="tour-availability">{kind==="monitoring" ? "Monitoring and delivery depend on configured sources and approved thresholds." : kind==="partner" ? "Partner capabilities are available in enabled partner deployments." : "The reader shows approved editions when available."}</div></>}
      </div>
    </div><div className="tour-caption"><span>Explore the product structure. No customer data or sample scores are shown.</span><span>Evidence by design <ArrowUpRight size={12}/></span></div>
  </div>;
}

export function ProductTour() {
  return <section className="product-tour-section site-section" id="product-tour"><div className="site-wrap"><Reveal><div className="site-section-heading"><div><Eyebrow>Inside the technology</Eyebrow><h2>See what you can<br /><em>do with the intelligence.</em></h2></div><p className="section-side-copy">A connected workspace for understanding disclosures, following change and delivering insight.</p></div></Reveal><Tabs.Root defaultValue="assessment" className="product-tour-tabs"><Tabs.List aria-label="Explore Visentix products" className="product-tab-list">{productCatalog.map(p=>{const Icon=icons[p.id];return <Tabs.Trigger key={p.id} value={p.id}><Icon size={17}/>{p.short}</Tabs.Trigger>;})}</Tabs.List>{productCatalog.map(p=><Tabs.Content key={p.id} value={p.id}><WorkspaceTour kind={p.id}/><div className="tour-product-link"><span>{p.audience}</span><SiteLink to={p.path} subtle>Explore {p.short.toLowerCase()}</SiteLink></div></Tabs.Content>)}</Tabs.Root></div></section>;
}

const plans = [
  { name: "Monitor", category: "FOR AN ONGOING VIEW", monthly: 299, annual: 239, text: "For teams establishing a regular view of their public disclosures.", features: ["Notice assessment workspace", "Monitoring and change-feed capabilities", "Assessment history", "Report access and PDF exports"] },
  { name: "Intelligence", category: "FOR DEEPER EXPLORATION", monthly: 799, annual: 639, text: "For teams bringing evidence and peer context into everyday decisions.", features: ["Assessment and monitoring capabilities", "Peer benchmark exploration", "Findings and evidence lineage", "Executive and analyst report views"] },
  { name: "Enterprise", category: "FOR YOUR CLIENTS & ORGANIZATION", monthly: null, annual: null, text: "For partners and organizations with a tailored delivery model.", features: ["Partner workspace capabilities", "White-label report delivery", "API requirements scoped together", "Agreed onboarding and delivery scope"] },
];
export function PlanComparison({ full = false }: { full?: boolean }) {
  const [annual, setAnnual] = useState(false);
  return <section id="plans" className="plans-section"><div className="site-wrap"><div className="site-section-heading"><div><Eyebrow>Plans & subscriptions</Eyebrow><h2>Start with your needs.<br /><em>Choose your perspective.</em></h2></div><div className="plans-billing" role="group" aria-label="Billing period"><button aria-pressed={!annual} onClick={()=>setAnnual(false)}>Monthly</button><button aria-pressed={annual} onClick={()=>setAnnual(true)}>Annual</button></div></div><p className="plans-intro">Indicative plans based on our initial offering. Pricing, allowances and availability are confirmed with your Visentix contact.</p><div className="plan-grid">{plans.map((p,i)=><article className={`plan-card ${i===1?"plan-featured":""}`} key={p.name}><span className="site-kicker">{p.category}</span><h3>{p.name}</h3><p>{p.text}</p><div className="plan-price">{p.monthly ? <><strong>${annual?p.annual:p.monthly}</strong><span>/ month</span></> : <strong>Let’s talk.</strong>}</div><span className="plan-price-note">{p.monthly ? (annual?"Indicative monthly equivalent · annual billing":"Indicative planning price · monthly billing") : "Custom scope and partner licensing"}</span><SiteLink to={`/contact?plan=${encodeURIComponent(p.name)}&billing=${annual?"annual":"monthly"}`}>{p.monthly?"Discuss this plan":"Contact us"}</SiteLink><div className="plan-features-heading">CAPABILITIES TO DISCUSS</div><ul>{p.features.map(f=><li key={f}><Check size={14}/>{f}</li>)}</ul></article>)}</div><div className="plans-footnote"><p>Monitoring requires configured sources. Partner features require an enabled deployment. No payment is collected online.</p>{!full&&<SiteLink to="/pricing" subtle>Compare plans & details</SiteLink>}</div></div></section>;
}

export function AudienceExplorer() {
  const audiences=[
    {name:"Privacy & legal teams",title:"Move from documents to decisions.",text:"Assess public notices with peer context. Explore findings, read the evidence and share an executive view with your stakeholders.",items:["Assess a public notice","Explore its benchmark context","Share an evidence-led report"]},
    {name:"Consultants & advisors",title:"Make the intelligence part of your service.",text:"Bring a structured assessment into your client work, then deliver the evidence through branded reports and partner workspaces.",items:["Manage client workspaces","Deliver branded intelligence","Scope partner access"]},
    {name:"Business leaders",title:"Get the context behind the headline.",text:"Understand disclosure maturity and exposure through reports that connect executive summaries with their supporting evidence.",items:["Read an executive overview","Understand confidence and scope","Follow the wider landscape"]},
  ];
  return <section className="audience-section site-section"><div className="site-wrap"><Eyebrow>Built for your role</Eyebrow><Tabs.Root defaultValue="0" className="audience-layout"><div><h2>Different responsibilities.<br /><em>One intelligence layer.</em></h2><Tabs.List aria-label="Choose your role" className="audience-tab-list">{audiences.map((a,i)=><Tabs.Trigger value={String(i)} key={a.name}>{a.name}<ArrowUpRight size={18}/></Tabs.Trigger>)}</Tabs.List></div>{audiences.map((a,i)=><Tabs.Content value={String(i)} key={a.name} className="audience-panel"><span className="site-kicker">{a.name}</span><h3>{a.title}</h3><p>{a.text}</p><ul>{a.items.map((t,j)=><li key={t}><span>0{j+1}</span>{t}</li>)}</ul><SiteLink to={i===1?"/solutions/white-label":"/solutions/notice-assessment"} subtle>Find your solution</SiteLink></Tabs.Content>)}</Tabs.Root></div></section>;
}

export function CapabilityRoadmap() {
  return <section className="site-section capability-section"><div className="site-wrap"><div className="site-section-heading"><div><Eyebrow>The next chapter</Eyebrow><h2>A platform with<br /><em>room to go further.</em></h2></div><p className="section-side-copy">Beyond the core products, we’re exploring more ways to turn disclosure evidence into useful workflows.</p></div><div className="capability-grid">{[["Framework Mapping","Preview","Explore how disclosure themes relate to selected frameworks."],["Vendor Assessment Workflows","Preview","Bring public-notice intelligence into a vendor evaluation workflow."],["Firm Collaboration","Planned","Shared oversight with firm-specific roles and responsibilities."]].map(([name,state,text])=><article key={name}><span className="capability-status">{state}</span><h3>{name}</h3><p>{text}</p><ArrowUpRight size={22}/></article>)}</div><p className="site-fine-print">Preview and planned capabilities are not included as committed plan features. Availability will be confirmed as each capability is released.</p></div></section>;
}
