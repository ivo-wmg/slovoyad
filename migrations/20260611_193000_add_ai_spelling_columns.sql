-- Add AI detection and spelling errors columns
ALTER TABLE evaluations
    ADD COLUMN ai_probability TINYINT UNSIGNED DEFAULT 0 AFTER weaknesses,
    ADD COLUMN ai_reasoning TEXT DEFAULT NULL AFTER ai_probability,
    ADD COLUMN spelling_errors JSON DEFAULT NULL AFTER ai_reasoning;
