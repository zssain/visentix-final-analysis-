import { Alert, AlertDescription } from "@/components/ui/alert";

/** Transient status banner — pair with the useFlash hook (lib/useFlash). */
export function FlashNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <Alert role="status" className="mb-4">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
