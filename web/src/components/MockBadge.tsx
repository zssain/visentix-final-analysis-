import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/**
 * Marks a surface whose numbers are illustrative, not measured.
 *
 * Placed at SURFACE level (panel, card, section) — never on each figure.
 * A badge on every number is noise; a badge on the panel is a fact.
 *
 * `id` is the MOCK TRACKER id (e.g. "M-18") so a reader — and a reviewer
 * grepping the tracker — can tie the badge to the register entry. Passing a
 * tracker id that does not exist is caught by scripts/check_mocks.py.
 *
 * Hard Rule 7 (honest numbers): an unlabelled illustrative figure in a report
 * a customer forwards is indistinguishable from a fabricated one.
 */
export function MockBadge({ id, className }: { id: string; className?: string }) {
  return (
    <Badge
      variant="provisional"
      className={className}
      title={`Illustrative data (${id}) — not measured from this organization`}
      data-mock-id={id}
    >
      <FlaskConical aria-hidden="true" />
      Illustrative data
      <span className="sr-only"> — {id}. These figures are examples, not measurements from this organization.</span>
    </Badge>
  );
}
