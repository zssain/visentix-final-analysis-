# The Rules We Never Break

Every product has features. Ours also has promises — rules baked so deep that breaking one isn't a bug, it's a betrayal of what customers are buying. New people: learn these before you learn anything else. They apply to code, reports, marketing copy, sales calls, and casual emails alike.

---

## Rule 1 — No legal verdicts. Ever.

We never say "compliant," "non-compliant," "violation," or "illegal." Not in reports, not in the UI, not in a tweet. We say *exposure, maturity, likelihood, benchmark position, regulator sensitivity, confidence*.

**Why:** we're not a law firm. The moment we issue a legal verdict, we take on liability we can't carry and lose the trust of the lawyers and regulators who like that we know our lane. This isn't hedging — the comparative framing IS the product.

**How it's enforced:** a banned-term filter checks every machine-generated sentence; the expert checks everything else; a small "Intelligence, not legal advice" mark sits on findings and reports. If you ever see verdict language anywhere, treat it like a fire alarm.

## Rule 2 — No score without a receipt.

Every number a customer sees must be clickable, and the click must reveal its lineage: the exact clause, the sources, the peer group, the formula, the confidence, the snapshot. If we can't show where a number came from, we don't show the number.

**Why:** our audience defends their own findings for a living. "Trust us" is worth nothing to them; "here's exactly how we got it" is worth everything.

## Rule 3 — Honest confidence, always.

Every score carries a confidence rating (VCI). Low confidence gets a visible label. Very low confidence gets suppressed — we'd rather say "we don't know yet" than dress up a guess. Small peer groups are flagged; we never display a fake or stale group size.

**Why:** one confidently-wrong number costs more trust than a hundred honest "low confidence" labels.

## Rule 4 — Delivered reports never change.

An approved report is frozen into a snapshot. Pull it again in five years: byte-identical. Improvements to our formulas apply to *new* work; history is never silently rewritten.

**Why:** professionals cite our reports in board meetings and negotiations. A deliverable that shifts under their feet is worthless.

## Rule 5 — A human expert stands between the machine and the client.

Client reports pass through expert review: every finding confirmed, edited, or dismissed by a human specialist. Drafts that skip review are loudly watermarked as drafts.

**Why:** the machine is the scale; the expert is the judgment. Customers are buying both.

## Rule 6 — Fair comparisons only.

Companies are compared to genuinely similar peers, similarity-weighted, with any compromise (a widened peer group) disclosed and the confidence lowered to match. We never grade a corner shop against a tech giant.

**Why:** an unfair benchmark isn't just unkind, it's wrong — and one wrong comparison poisons faith in every right one.

## Rule 7 — Other people's data is treated better than they'd expect.

Customer notices stay in the customer's walls. Anything reused across customers (example language, benchmark stats, published numbers) is anonymized first, and the system physically blocks reuse of language still containing names, emails, or addresses. Published statistics only come from groups large enough that no company can be picked out.

**Why:** we're a *privacy* company. Being sloppy with data would be self-parody — and fatal.

## Rule 8 — The AI assists; it doesn't decide.

AI reads, sorts, and drafts. It does not compute final scores (formulas do), does not approve anything (the expert does), and its every output records what model and confidence produced it. AI-drafted prose passes the guardrail filter, with a plain deterministic fallback if the fancy wording fails the check.

**Why:** determinism and accountability are what make our numbers defensible. "The AI said so" is never an acceptable lineage.

## Rule 9 — Speak the reader's language.

Customer screens use plain English — no security jargon, no internal shorthand, no naming the attack classes we defend against. Internal expert screens may use precise technical terms. Same facts, different register, always deliberate.

**Why:** jargon on a customer screen reads as noise at best and as showing off at worst.

## Rule 10 — Specs before code; docs match reality.

Nothing gets built without a written spec the expert has seen. If reality and the document disagree, fixing the document is part of fixing the problem. (Full method in `09-how-we-build.md`.)

**Why:** with two engineers and heavy AI assistance, written truth is the only thing keeping everyone — humans and AI agents — building the same product.

---

## If you're ever unsure

Ask: *"Would I be comfortable explaining this choice to a skeptical regulator, with the receipts on the table?"* If yes, proceed. If no, stop and ask the expert. Nobody at Visentix has ever gotten in trouble for pausing to ask.
