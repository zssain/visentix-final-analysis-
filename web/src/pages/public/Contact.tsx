import { useSearchParams } from "react-router-dom";
import { PageIntro, SiteLink } from "./shared";
export function Contact() {
  const [params] = useSearchParams();
  const requestedPlan = params.get("plan");
  const plan = ["Monitor", "Intelligence", "Enterprise"].includes(requestedPlan ?? "") ? requestedPlan : null;
  return <><PageIntro eyebrow="Connect with Visentix" title={<>A conversation starts<br /><em>with perspective.</em></>}><p>For questions about notice assessments, monitoring or partner intelligence, speak with your existing Visentix contact.</p></PageIntro>{plan && <div className="site-wrap"><div className="contact-plan-context"><span className="site-kicker">YOUR PLAN INTEREST</span><h2>{plan}</h2><p>{params.get("billing") === "annual" ? "Annual billing preference" : params.get("billing") === "monthly" ? "Monthly billing preference" : "Partner licensing enquiry"}. This selection is shown for your reference; no enquiry has been sent.</p><SiteLink to="/pricing" subtle>Compare other plans</SiteLink></div></div>}<section className="site-wrap site-contact-section"><div className="site-contact-note"><span className="site-kicker">Enquiries</span><h2>Online enquiries are not available yet</h2><p>Please use your existing Visentix contact. This page does not collect or send messages.</p></div><div><span className="site-kicker">Already have an account?</span><h2>Your workspace<br /><em>is ready for you.</em></h2><p>Sign in to access your assessments and available tools.</p><SiteLink to="/login">Sign in</SiteLink></div></section></>;
}
