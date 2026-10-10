ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_text TEXT;
CREATE INDEX IF NOT EXISTS document_chunks_search_text_trgm ON document_chunks USING GIN (search_text gin_trgm_ops);
