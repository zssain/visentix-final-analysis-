/** Shared typographic identity; inherits the surface's accessible foreground. */
export function VisentixWordmark({ className = "" }: { className?: string }) {
  return <span role="img" aria-label="Visentix" className={`inline-block shrink-0 select-none text-[32px] leading-none tracking-[-0.085em] ${className}`}
    style={{ fontFamily: "Arial, Helvetica, sans-serif", fontWeight: 600 }}>
    visentix.
  </span>;
}
