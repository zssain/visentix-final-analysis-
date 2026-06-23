/**
 * API client tests — verifies no service-role key in frontend code.
 */
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("API client security", () => {
  const srcDir = path.resolve(__dirname, "..");

  function readAllFiles(dir: string): string[] {
    const files: string[] = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== "node_modules" && entry.name !== "test") {
        files.push(...readAllFiles(full));
      } else if (entry.isFile() && /\.(ts|tsx)$/.test(entry.name)) {
        files.push(full);
      }
    }
    return files;
  }

  it("never references service_role_key in frontend code", () => {
    const files = readAllFiles(srcDir);
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      expect(content).not.toContain("service_role");
      expect(content).not.toContain("SERVICE_ROLE");
    }
  });

  it("never references SUPABASE_SERVICE_ROLE_KEY in frontend code", () => {
    const files = readAllFiles(srcDir);
    for (const file of files) {
      const content = fs.readFileSync(file, "utf-8");
      expect(content).not.toContain("SUPABASE_SERVICE_ROLE_KEY");
    }
  });

  it("only uses VITE_ prefixed env vars", () => {
    const apiFile = fs.readFileSync(path.resolve(srcDir, "lib/api.ts"), "utf-8");
    const supabaseFile = fs.readFileSync(path.resolve(srcDir, "lib/supabase.ts"), "utf-8");
    const combined = apiFile + supabaseFile;

    // All import.meta.env references should use VITE_ prefix
    const envRefs = combined.match(/import\.meta\.env\.\w+/g) || [];
    for (const ref of envRefs) {
      expect(ref).toMatch(/import\.meta\.env\.VITE_/);
    }
  });
});
