import ts from "typescript";
import { readFileSync } from "node:fs";
const src = readFileSync(process.argv[2], "utf8");
const sf = ts.createSourceFile(process.argv[2], src, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
// @ts-ignore — parseDiagnostics is internal but is exactly the syntax-error list
const errs = sf.parseDiagnostics ?? [];
if (errs.length) { console.error(errs.slice(0,3).map(e=>ts.flattenDiagnosticMessageText(e.messageText,' ')).join('; ')); process.exit(1); }
