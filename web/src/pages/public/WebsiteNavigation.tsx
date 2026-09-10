import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Popover } from "radix-ui";
import { ArrowUpRight, ChevronDown, FileText, Activity, Users, BookOpen } from "lucide-react";
import { productCatalog } from "./products";
const icons=[FileText,Activity,Users,BookOpen];
export function WebsiteNavigation() {
  const [open,setOpen]=useState<string|null>(null);
  const {pathname}=useLocation();
  return <nav aria-label="Website" className="website-navigation">
    <Popover.Root open={open==="products"} onOpenChange={v=>setOpen(v?"products":null)}><Popover.Trigger className="website-nav-trigger">Products<ChevronDown size={13}/></Popover.Trigger><Popover.Portal><Popover.Content className="public-site site-popover" aria-label="Products menu" sideOffset={18} collisionPadding={24} align="center" onOpenAutoFocus={e=>e.preventDefault()}><div className="popover-feature"><span className="site-kicker">FOUR PRODUCTS. ONE ENGINE.</span><h2>Privacy intelligence,<br /><em>put to work.</em></h2><p>From your first assessment to the service you deliver to clients.</p><Link to="/solutions" onClick={()=>setOpen(null)}>Explore all products<ArrowUpRight size={17}/></Link></div><div className="popover-product-links">{productCatalog.map((p,i)=>{const Icon=icons[i];return <Link to={p.path} key={p.id} onClick={()=>setOpen(null)}><span className={`popover-icon tone-${p.tone}`}><Icon size={19}/></span><span><strong>{p.short}</strong><small>{p.category}</small></span><ArrowUpRight size={16}/></Link>;})}</div><div className="popover-bottom"><span>Built on evidence. Delivered through your workspace.</span><Link to="/pricing" onClick={()=>setOpen(null)}>Plans & subscriptions<ArrowUpRight size={14}/></Link></div></Popover.Content></Popover.Portal></Popover.Root>
    <Link to="/platform" aria-current={pathname==="/platform"?"page":undefined} onClick={()=>setOpen(null)}>Platform</Link>
    <Link to="/pricing" aria-current={pathname==="/pricing"?"page":undefined} onClick={()=>setOpen(null)}>Plans</Link>
    <Popover.Root open={open==="resources"} onOpenChange={v=>setOpen(v?"resources":null)}><Popover.Trigger className="website-nav-trigger">Resources<ChevronDown size={13}/></Popover.Trigger><Popover.Portal><Popover.Content className="public-site site-popover resources-popover" aria-label="Resources menu" sideOffset={18} collisionPadding={24} onOpenAutoFocus={e=>e.preventDefault()}><span className="site-kicker">EXPLORE VISENTIX</span>{[["Resource library","/resources"],["Quarterly intelligence","/solutions/quarterly-report"],["Our methodology","/methodology"],["Our approach","/about"]].map(([name,to])=><Link to={to} onClick={()=>setOpen(null)} key={to}>{name}<ArrowUpRight size={17}/></Link>)}</Popover.Content></Popover.Portal></Popover.Root>
  </nav>;
}
