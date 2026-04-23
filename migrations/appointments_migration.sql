-- Migration: Add date/start_time/end_time columns to appointments
-- Run this SQL against your PostgreSQL database

-- 1. Add new columns as nullable first
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS date DATE;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS start_time TIME;
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS end_time TIME;

-- 2. Migrate data from datetime (if exists and has data)
-- Assuming there's a 'datetime' column with old datetime values
UPDATE appointments 
SET 
    date = (datetime AT TIME ZONE 'UTC')::date,
    start_time = (datetime AT TIME ZONE 'UTC')::time,
    end_time = (datetime AT TIME ZONE 'UTC' + (duration_minutes || ' minutes')::interval)::time
WHERE datetime IS NOT NULL;

-- 3. Remove old datetime column (optional - comment out if you want to keep it temporarily)
-- ALTER TABLE appointments DROP COLUMN IF EXISTS datetime;