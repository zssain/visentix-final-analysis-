import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Transient status message with a self-clearing timer.
 * Replaces the four copy-pasted flash implementations (audit 2026-07-16) and
 * fixes their shared bug: an older timer could clear a newer message early.
 */
export function useFlash(durationMs = 4000): [string | null, (msg: string) => void] {
  const [flash, setFlash] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = useCallback((msg: string) => {
    if (timer.current) clearTimeout(timer.current);
    setFlash(msg);
    timer.current = setTimeout(() => setFlash(null), durationMs);
  }, [durationMs]);

  // Clear any pending timer on unmount.
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  return [flash, show];
}
