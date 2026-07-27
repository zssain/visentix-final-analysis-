-- Migration 0033: intake provenance on privacy_notice (F01 — upload intake mode)
-- ADDITIVE ONLY. Idempotent.
--
-- F01 gains a third intake mode: uploaded documents (PDF / DOCX / TXT), alongside
-- URL and paste-text. An uploaded document is NOT a verified source (that badge
-- means a URL passed SSRF validation), so it must be recorded honestly for what
-- it is: an "uploaded document" with its own filename, MIME, and original-file
-- hash. schema.md §2.4 declares privacy_notice.intake_method (url/pdf/text) +
-- ssrf_protected, but the live table has neither column — the router returned
-- them in the response only. This adds intake_method plus the upload-specific
-- provenance columns so the source register reflects real capture facts.
--
-- Columns are NULL for existing rows and for url/text intake; set only on upload.

ALTER TABLE privacy_notice
    ADD COLUMN IF NOT EXISTS intake_method    TEXT,
    ADD COLUMN IF NOT EXISTS upload_filename  TEXT,
    ADD COLUMN IF NOT EXISTS upload_mime      TEXT,
    ADD COLUMN IF NOT EXISTS upload_file_hash TEXT;

-- Bound intake_method to the known capture modes (NULL allowed for legacy rows).
ALTER TABLE privacy_notice DROP CONSTRAINT IF EXISTS privacy_notice_intake_method_check;
ALTER TABLE privacy_notice
    ADD CONSTRAINT privacy_notice_intake_method_check
    CHECK (intake_method IS NULL OR intake_method IN ('url', 'text', 'upload'));
