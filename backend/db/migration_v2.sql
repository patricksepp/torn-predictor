-- Migration v2: add new high-signal personalstats columns to training_data.
-- trainsreceived is intentionally excluded — employer trains give JOB stats
-- (INT/MAN/END), not battle stats (STR/DEF/SPD/DEX).
-- Run in the Supabase SQL editor before retraining.

ALTER TABLE training_data ADD COLUMN IF NOT EXISTS candyused       INTEGER;
ALTER TABLE training_data ADD COLUMN IF NOT EXISTS useractivity    BIGINT;
ALTER TABLE training_data ADD COLUMN IF NOT EXISTS daysbeendonator INTEGER;
