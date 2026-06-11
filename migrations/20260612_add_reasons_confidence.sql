-- Migration: Add confidence column to evaluations
-- Date: 2026-06-12

ALTER TABLE evaluations ADD COLUMN confidence INT DEFAULT NULL AFTER ai_reasoning;
