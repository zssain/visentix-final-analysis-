import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { ClosingNote, PageIntro, Reveal } from "./shared";
export function Resources() {
  return <><PageIntro eyebrow="Resources & perspectives" title={<>Look closer.<br /><em>Understand more.</em></>}><p>Explore the approach, definitions and published evidence behind Visentix intelligence.</p></PageIntro><section className="site-wrap site-resource-list">{[
    ["01", "The method", "How the intelligence takes shape.", "Explore versioned formulas, evidence lineage, confidence and expert review.", "/methodology", "Read the methodology"],
    ["02", "The definitions", "A shared language for findings.", "Find definitions and source references in the application’s finding dictionary. Sign in to access the catalog.", "/finding-codes", "Explore finding definitions"],
    ["03", "The wider view", "Quarterly privacy intelligence.", "Check the reader for approved publications. Availability and the scope of each edition are shown there.", "/quarterly", "Open the quarterly reader"],
  ].map(([num, label, title, text, to, cta]) => <Reveal key={num}><Link to={to} className="site-resource-row"><span className="site-index">{num} / {label}</span><div><h2>{title}</h2><p>{text}</p><span className="site-inline-arrow">{cta}<ArrowUpRight size={17} /></span></div><ArrowUpRight className="site-resource-arrow" /></Link></Reveal>)}</section><ClosingNote /></>;
}
