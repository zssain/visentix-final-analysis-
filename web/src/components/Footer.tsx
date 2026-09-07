import { Link } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import { PoweredByTeclusion } from "@/components/PoweredByTeclusion";

/**
 * Global footer — legal links required for launch (/privacy, /terms). Public,
 * unauthenticated, present on every route.
 */
export function Footer() {
  const year = new Date().getFullYear();
  return (
    <>
      <Separator className="mt-12" />
      <footer className="flex flex-wrap items-center justify-between gap-4 px-6 py-5 text-xs text-muted-foreground">
        <span className="flex items-center gap-3">© {year} Visentix <PoweredByTeclusion /></span>
        <nav className="flex gap-4" aria-label="Legal">
          <Link to="/privacy" className="text-foreground/70 hover:text-foreground transition-colors">Privacy</Link>
          <Link to="/terms" className="text-foreground/70 hover:text-foreground transition-colors">Terms</Link>
          <Link to="/methodology" className="text-foreground/70 hover:text-foreground transition-colors">Methodology</Link>
        </nav>
      </footer>
    </>
  );
}
