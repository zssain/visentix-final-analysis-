import "./furniture.css";

/** Transient status banner — pair with the useFlash hook (lib/useFlash). */
export function FlashNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="flash-notice" role="status">{message}</div>;
}
