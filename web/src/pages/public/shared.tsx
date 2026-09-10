import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ArrowUpRight } from "lucide-react";

export function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    if (!ref.current || !window.IntersectionObserver || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const node = ref.current;
    if (node.getBoundingClientRect().top < window.innerHeight) return;
    setVisible(false);
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, { threshold: 0.08 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return <div ref={ref} className={`site-reveal ${visible ? "is-visible" : ""} ${className}`}>{children}</div>;
}

export function SiteLink({ to, children, subtle = false }: { to: string; children: ReactNode; subtle?: boolean }) {
  return <Link to={to} className={subtle ? "site-text-link" : "site-button"}>{children}<ArrowUpRight size={18} aria-hidden="true" /></Link>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="site-eyebrow"><span aria-hidden="true" />{children}</div>;
}

/** Original decorative architecture: perspective and layers, never a data plot. */
export function PerspectiveArt({ compact = false }: { compact?: boolean }) {
  return <div className={`perspective-art ${compact ? "is-compact" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 600 680" fill="none" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={compact ? "stone-small" : "stone"} x1="140" y1="70" x2="520" y2="630" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--site-art-light)" /><stop offset=".52" stopColor="var(--site-art-mid)" /><stop offset="1" stopColor="var(--site-forest)" />
        </linearGradient>
        <linearGradient id={compact ? "ground-small" : "ground"} x1="0" y1="480" x2="600" y2="680" gradientUnits="userSpaceOnUse">
          <stop stopColor="var(--site-art-mid)" /><stop offset="1" stopColor="var(--site-deep)" />
        </linearGradient>
      </defs>
      <path fill="var(--site-deep)" d="M0 0h600v680H0z" />
      <path d="M0 470 600 400v280H0Z" fill={`url(#${compact ? "ground-small" : "ground"})`} />
      {Array.from({ length: 18 }, (_, i) => <path key={`floor-${i}`} d={`M${-700 + i * 100} 680 340 400`} stroke="var(--site-art-light)" opacity=".12" />)}
      <path d="m138 558 239-55 223 96v81H338Z" fill="var(--site-art-shadow)" opacity=".55" />
      <g className="art-portal">
        <path d="M114 559V237C114 84 363 19 439 171c18 36 24 67 24 111v225l-69 17V283c0-126-152-121-152 0v246Z" fill={`url(#${compact ? "stone-small" : "stone"})`} />
        {Array.from({ length: 26 }, (_, i) => {
          const x = 116 + i * 4.7;
          const y = 239 + i * 1.75;
          return <path key={i} d={`M${x} ${559-i*1.18}V${y}C${x} ${83+i*6.15} ${438-i*5.75} ${30+i*6.2} ${438-i*1.75} ${219+i*2.46}V${514+i*.5}`} stroke="var(--site-paper)" strokeWidth=".8" opacity={.16+i*.014} />;
        })}
        <path d="M243 529V283c0-120 151-126 151 0v241l-40-38V288c0-62-65-63-65 0v231Z" fill="var(--site-art-shadow)" />
        <path d="M294 514V309a28 28 0 0 1 56 0v189Z" fill="var(--site-lime)" />
        <path d="m294 514 56-16 113 52-92 26Z" fill="var(--site-lime)" opacity=".22" />
      </g>
      <path d="M38 38h20M38 38v20M562 38h-20M562 38v20M38 642h20M38 642v-20M562 642h-20M562 642v-20" stroke="var(--site-art-light)" opacity=".6" />
      <circle cx="519" cy="84" r="4" fill="var(--site-lime)" />
      <path d="M508 84h-90" stroke="var(--site-art-light)" opacity=".45" />
    </svg>
    <span className="art-label">A different perspective.</span>
  </div>;
}

export const PRODUCTS = [
  { title: "Privacy Notice Assessment", description: "Understand what a public notice says, how it compares, and the evidence behind its assessment.", to: "/solutions/notice-assessment", tag: "ASSESS & UNDERSTAND" },
  { title: "Continuous Monitoring", description: "Follow changes across assessed notices. Monitoring and alerts depend on configured sources and available evidence.", to: "/solutions/continuous-monitoring", tag: "MONITOR & OBSERVE" },
  { title: "White-Label Intelligence", description: "Bring branded assessment reports into your client relationships through an enabled partner workspace.", to: "/solutions/white-label", tag: "PARTNER & DELIVER" },
  { title: "Quarterly Intelligence Report", description: "Explore approved quarterly publications on disclosure maturity, AI disclosure and enforcement themes.", to: "/solutions/quarterly-report", tag: "EXPLORE & INFORM" },
];

export function ProductCards() {
  return <div className="site-product-list">{PRODUCTS.map((product, i) => <Link key={product.to} to={product.to} className="site-product">
    <span className="site-index">0{i+1}</span><div><span className="site-kicker">{product.tag}</span><h3>{product.title}</h3><p>{product.description}</p></div><ArrowUpRight aria-hidden="true" />
  </Link>)}</div>;
}

export function Pipeline() {
  return <div className="site-pipeline">{[
    ["The source", "Start with what is disclosed.", "A public notice becomes structured clauses, with source references retained."],
    ["The context", "Comparison gives it meaning.", "Eligible peers and recorded signals put disclosure maturity and exposure in perspective."],
    ["The intelligence", "Follow the evidence.", "A report brings together findings, confidence and traceable reasoning. Draft status stays explicit."],
  ].map(([label, title, text], i) => <div key={label}><span className="site-index">0{i+1} / {label}</span><h3>{title}</h3><p>{text}</p>{i<2 && <ArrowRight aria-hidden="true" />}</div>)}</div>;
}

export function PageIntro({ eyebrow, title, children, art = false }: { eyebrow: string; title: ReactNode; children: ReactNode; art?: boolean }) {
  return <section className={`site-page-intro site-wrap ${art ? "with-art" : ""}`}><div><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1><div className="site-intro-copy">{children}</div></div>{art && <PerspectiveArt compact />}</section>;
}

export function ClosingNote() {
  return <section className="site-closing"><div className="site-wrap"><Eyebrow>Clarity starts here</Eyebrow><div><h2>Put your privacy notice<br />in <em>perspective.</em></h2><SiteLink to="/workspace">Open your workspace</SiteLink></div><p>Already have an account? Your next assessment starts with a notice.</p></div></section>;
}
