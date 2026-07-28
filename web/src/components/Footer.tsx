import { Link } from "react-router-dom";

/**
 * Global footer — legal links required for launch (/privacy, /terms). Public,
 * unauthenticated, present on every route.
 */
export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer style={{
      borderTop: "1px solid var(--border)",
      marginTop: 48,
      padding: "20px 24px",
      display: "flex",
      flexWrap: "wrap",
      gap: 16,
      alignItems: "center",
      justifyContent: "space-between",
      fontSize: "0.8rem",
      color: "var(--text-muted)",
    }}>
      <span>© {year} Visentix — privacy intelligence, not legal advice.</span>
      <nav style={{ display: "flex", gap: 18 }} aria-label="Legal">
        <Link to="/privacy" style={{ color: "var(--text-secondary)" }}>Privacy</Link>
        <Link to="/terms" style={{ color: "var(--text-secondary)" }}>Terms</Link>
        <Link to="/methodology" style={{ color: "var(--text-secondary)" }}>Methodology</Link>
      </nav>
    </footer>
  );
}
