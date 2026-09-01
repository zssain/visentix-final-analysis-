/**
 * Quarterly admin table — the status column.
 *
 * The label said "Draft — gold watermark", which named a PDF rendering detail
 * on a badge that is already gold. That was the visible problem. The one that
 * mattered was underneath it: the label came from
 * `status === "draft" ? … : "Approved"`, so EVERY status that is not literally
 * "draft" rendered as Approved — and on this table Approved is the difference
 * between "nobody may see this" and "this is public".
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "@/components/ui/badge";
import { statusLabel } from "../lib/labels";

/* The component's own maps, mirrored here so the rule is testable without
   standing up the whole admin panel (which needs auth + four endpoints). The
   guard below keeps this copy honest. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const RAW = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../pages/quarterly/QuarterlyReport.tsx"),
  "utf-8",
);

/* Comments stripped before matching. The file explains what the old label said
   and why it was wrong, and a naive search would find the explanation and call
   it a regression — a guard that cannot tell a fix from the note recording it
   is a guard nobody can write a comment near. */
const SOURCE = RAW.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

describe("quarterly snapshot status", () => {
  it("no longer describes the PDF's watermark where the state belongs", () => {
    expect(SOURCE).not.toMatch(/"Draft — gold watermark"/);
  });

  it("labels come from the governed registry, not an inline ternary", () => {
    // The ternary is what made every non-draft status read as "Approved".
    expect(SOURCE).toMatch(/statusLabel\(s\.status\)/);
    expect(SOURCE).not.toMatch(/s\.status === "draft" \? "[^"]*" : "Approved"/);
  });

  it("an unrecognised status is never labelled Approved", () => {
    // "Approved" on this table means published. A status the UI does not
    // recognise must not inherit the most permissive reading of itself.
    expect(statusLabel("superseded")).not.toBe("Approved");
    expect(statusLabel("withdrawn")).not.toBe("Approved");
    expect(statusLabel("")).toBe("Not recorded");
  });

  it("renders the two real states with the governed KIND variants", () => {
    render(
      <>
        <Badge variant="provisional">{statusLabel("draft")}</Badge>
        <Badge variant="verified">{statusLabel("approved")}</Badge>
      </>
    );
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("Approve is offered only for a draft whose gate actually passed", () => {
    // `passed` is undefined when no gate has run. The old expression relied on
    // `&& undefined` rendering nothing — correct, but by accident.
    expect(SOURCE).toMatch(/const canApprove = s\.status === "draft" && passed === true;/);
  });

  it("a gate that has not run is stated, not shown as an em dash", () => {
    // A dash in a verdict column is indistinguishable from a missing cell.
    expect(SOURCE).toMatch(/Not run/);
  });
});
