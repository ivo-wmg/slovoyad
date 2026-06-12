-- Add recommendations column (JSON array of up to 3 actionable suggestions)
ALTER TABLE evaluations ADD COLUMN recommendations TEXT DEFAULT NULL AFTER weaknesses;
