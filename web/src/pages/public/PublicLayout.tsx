import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowUpRight, Menu } from "lucide-react";
import { WebsiteNavigation } from "./WebsiteNavigation";
import { productCatalog } from "./products";
import { Sheet, SheetContent, SheetTitle, SheetTrigger, SheetClose } from "@/components/ui/sheet";
import { useAuth } from "@/auth/AuthProvider";
import "./website.css";
import "./product-site.css";

const NAV = [["Platform", "/platform"], ["All products", "/solutions"], ["Plans & subscriptions", "/pricing"], ["Our approach", "/about"], ["Resources", "/resources"], ["Contact", "/contact"]];
export function PublicLayout({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { pathname, hash } = useLocation();
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [pathname, hash]);
  useEffect(() => {
    const titles: Record<string, string> = {
      "/": "Privacy. In perspective.", "/platform": "The platform", "/solutions": "Solutions",
      "/about": "Our approach", "/resources": "Resources", "/contact": "Contact",
      "/pricing": "Plans & subscriptions", "/solutions/continuous-monitoring": "Continuous Monitoring", "/solutions/white-label": "White-Label Intelligence",
      "/solutions/notice-assessment": "Notice intelligence", "/solutions/quarterly-report": "Quarterly intelligence",
    };
    const originalTitle = document.title;
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    const originalIcon = icon?.getAttribute("href");
    const originalType = icon?.getAttribute("type");
    document.title = `${titles[pathname] ?? "Privacy intelligence"} — Visentix`;
    if (icon) { icon.href = "/visentix-site.svg"; icon.type = "image/svg+xml"; }
    return () => {
      document.title = originalTitle;
      if (icon && originalIcon) icon.setAttribute("href", originalIcon);
      if (icon && originalType) icon.setAttribute("type", originalType);
    };
  }, [pathname]);
  const close = () => setMobile(false);
  const destination = session ? "/workspace" : "/login";
  return <div className="public-site">
    <a href="#public-content" className="site-skip">Skip to content</a>
    <header className="site-header">
      <div className="site-header-inner">
        <Link to="/" aria-label="Visentix home" className="site-wordmark" onClick={close}>visentix<span>.</span></Link>
        <WebsiteNavigation />
        <div className="site-header-actions"><Link to="/contact" className="header-contact">Contact us <ArrowUpRight size={14}/></Link><Link to={destination} className="site-login">{session ? "Open workspace" : "Log in"}<ArrowUpRight size={16} aria-hidden="true" /></Link>
          <Sheet open={mobile} onOpenChange={setMobile}><SheetTrigger className="site-mobile-trigger" aria-label="Open website menu"><Menu size={23} /></SheetTrigger>
            <SheetContent className="public-site public-drawer"><SheetTitle className="site-wordmark">visentix.</SheetTitle><nav aria-label="Mobile website">{NAV.map(([label,to]) => <SheetClose asChild key={to}><Link to={to}>{label}<ArrowUpRight size={19} /></Link></SheetClose>)}<div className="mobile-product-links"><span className="site-kicker">OUR PRODUCTS</span>{productCatalog.map(p=><SheetClose asChild key={p.id}><Link to={p.path}>{p.short}<ArrowUpRight size={15}/></Link></SheetClose>)}</div></nav><p>Privacy intelligence.<br />A clearer perspective.</p></SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
    <main id="public-content" tabIndex={-1}>{children}</main>
    <footer className="site-footer">
      <div className="site-wrap">
        <div className="site-footer-top"><p>Privacy intelligence.<br /><em>A clearer perspective.</em></p><Link to="/about" className="site-footer-approach">Discover our approach<ArrowUpRight size={20} /></Link></div>
        <div className="site-footer-grid"><div><span className="site-kicker">What we do</span><Link to="/platform">The platform</Link><Link to="/solutions/notice-assessment">Notice assessment</Link><Link to="/solutions/continuous-monitoring">Continuous monitoring</Link><Link to="/solutions/white-label">White-label intelligence</Link><Link to="/solutions/quarterly-report">Quarterly intelligence</Link></div>
          <div><span className="site-kicker">Explore</span><Link to="/about">Our approach</Link><Link to="/resources">Resources</Link><Link to="/methodology">Methodology</Link><Link to="/pricing">Plans & subscriptions</Link><Link to="/contact">Contact</Link></div>
          <div><span className="site-kicker">Your workspace</span><Link to={destination}>{session ? "Open workspace" : "Sign in"}</Link><Link to="/privacy">Privacy notice</Link><Link to="/terms">Terms of use</Link></div>
          <div className="site-footer-statement"><span className="site-kicker">Our point of view</span><p>Compared to whom.<br />With what exposure.<br />At what confidence.</p><span>Evidence gives intelligence its value.</span></div>
        </div>
        <div className="site-footer-wordmark" aria-hidden="true">visentix<span>.</span></div>
        <div className="site-footer-bottom"><span>© {new Date().getFullYear()} Visentix</span><span>Privacy intelligence, grounded in evidence.</span><span>Technology by TeclusionAI</span></div>
      </div>
    </footer>
  </div>;
}
