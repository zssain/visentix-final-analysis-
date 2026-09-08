/** "Powered by Teclusion AI" mark — the Teclusion globe + label.
 *  The logo art has a transparent ground, so it reads cleanly on both light and
 *  dark surfaces without a chip. */
export function PoweredByTeclusion({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-muted-foreground ${className}`}>
      <img
        src="/teclusion-logo.png"
        alt=""
        aria-hidden="true"
        className="h-4 w-4"
      />
      Powered by Teclusion&nbsp;AI
    </span>
  );
}
