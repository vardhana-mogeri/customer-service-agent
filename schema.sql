-- This script defines the complete database schema for the customer support agent.
-- It is designed to be run multiple times safely.

-- Ensure required extensions are enabled. The user must have these installed
-- in their PostgreSQL instance for these commands to succeed.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS age;

-- Drop existing tables in reverse order of dependency to ensure a clean setup.
-- The 'CASCADE' option will automatically remove any dependent objects.
DROP TABLE IF EXISTS pg_docs CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;

-- Table for storing support tickets (System of Record)
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    ticket_id VARCHAR(50) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'Open',
    description TEXT,
    log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for the knowledge base documents and their vector embeddings (RAG)
-- The vector dimension (384) must match the embedding model used (e.g., 'all-MiniLM-L6-v2').
CREATE TABLE pg_docs (
    id SERIAL PRIMARY KEY,
    title TEXT,
    url TEXT UNIQUE, -- Added UNIQUE constraint to prevent duplicate document URLs
    content TEXT,
    embedding VECTOR(384)
);

-- Optional but highly recommended: Create an index on the embedding column for faster similarity searches.
-- HNSW (Hierarchical Navigable Small World) is a modern, fast index type for vector data.
-- This uses L2 distance, which is appropriate for the sentence-transformer models.
CREATE INDEX ON pg_docs USING HNSW (embedding vector_l2_ops);

-- Idempotently create the graph for Apache AGE conversation history.
-- We check for its existence before creating it.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'customer_support_graph') THEN
        PERFORM create_graph('customer_support_graph');
    END IF;
END
$$;

-- Inform the user that the schema setup is complete.
-- In psql, this will print a notice. When run from the Python script, it will be ignored.
\echo 'Schema setup complete: tables (tickets, pg_docs) and graph (customer_support_graph) are ready.'