-- Migration 001: lisa target_name predictions_cache tabelisse
ALTER TABLE predictions_cache ADD COLUMN IF NOT EXISTS target_name TEXT;
