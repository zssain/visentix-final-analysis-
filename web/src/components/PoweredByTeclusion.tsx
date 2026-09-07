/** "Powered by Teclusion AI" mark — the Teclusion globe + label.
 *  The logo art sits on a white ground, so on dark surfaces pass a light chip
 *  via `chip` to keep it clean; on light surfaces the bare logo reads fine. */
export function PoweredByTeclusion({
  className = "",
  chip = false,
}: {
  className?: string;
  chip?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-muted-foreground ${className}`}>
      <img
        src="/teclusion-logo.png"
        alt=""
        aria-hidden="true"
        className={chip ? "h-4 w-4 rounded-sm bg-white p-0.5" : "h-4 w-4 rounded-sm"}
      />
      Powered by Teclusion&nbsp;AI
    </span>
  );
}
