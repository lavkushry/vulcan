-- ============================================================================
-- Project Vulcan: Production PostgreSQL 16 + pgvector Catalog Schema Migration
-- Migration: 004_catalog_pgvector.sql
-- ============================================================================

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Catalog Items table with 1536-dim vector, tsvector generated column, and Steel Cage check constraint
CREATE TABLE IF NOT EXISTS catalog_items (
    id VARCHAR(64) PRIMARY KEY,
    identifier VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    engine VARCHAR(32) NOT NULL, -- 'ansible' | 'terraform' | 'script'
    git_repo VARCHAR(255) NOT NULL DEFAULT '',
    git_commit_sha VARCHAR(64),
    playbook_or_module_path VARCHAR(255) NOT NULL DEFAULT '',
    risk_tier VARCHAR(16) NOT NULL DEFAULT 'MEDIUM', -- 'LOW' | 'MEDIUM' | 'HIGH'
    requires_maker_checker BOOLEAN NOT NULL DEFAULT TRUE,
    requires_chg BOOLEAN NOT NULL DEFAULT TRUE,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_path VARCHAR(255),
    category VARCHAR(64) DEFAULT 'general',
    description TEXT DEFAULT '',
    tags TEXT[] DEFAULT '{}',
    curation_status VARCHAR(32) NOT NULL DEFAULT 'CANDIDATE',
    provenance JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, '') || ' ' || coalesce(identifier, ''))
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_catalog_curated_sha CHECK (curation_status <> 'CURATED' OR (git_commit_sha IS NOT NULL AND git_commit_sha ~ '^[0-9a-f]{40}$'))
);

-- 3. HNSW Vector Index for cosine distance ANN retrieval
CREATE INDEX IF NOT EXISTS idx_catalog_items_embedding_hnsw 
ON catalog_items USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Sparse Keyword Full-Text Search GIN Index
CREATE INDEX IF NOT EXISTS idx_catalog_items_tsv 
ON catalog_items USING gin(tsv);

-- 5. Metadata and Governance Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_items_curation ON catalog_items(curation_status);
CREATE INDEX IF NOT EXISTS idx_catalog_items_engine ON catalog_items(engine);
CREATE INDEX IF NOT EXISTS idx_catalog_items_risk ON catalog_items(risk_tier);
CREATE INDEX IF NOT EXISTS idx_catalog_items_category ON catalog_items(category);
CREATE INDEX IF NOT EXISTS idx_catalog_items_identifier ON catalog_items(identifier);
