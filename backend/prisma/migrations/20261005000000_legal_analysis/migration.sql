ALTER TABLE classification_searches ADD COLUMN legal_analysis jsonb NOT NULL DEFAULT '{}'::jsonb;
