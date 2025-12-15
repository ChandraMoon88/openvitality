-- =====================================================================
-- OpenVitality AI - Application Core Database Schema
-- =====================================================================
-- This schema stores core application data, including user information,
-- session state, dialogue history, and knowledge base content.
-- =====================================================================

-- Enable UUID extension for generating unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================
-- USERS & SESSIONS
-- =====================================================================

-- Table to store user/patient information
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- An external identifier, e.g., from an authentication service or telephony system
    external_id VARCHAR(255) UNIQUE,
    
    -- Basic profile information (can be extended as needed)
    profile JSONB -- e.g., {'name': 'John Doe', 'region': 'US', 'language_preference': 'en'}
);

CREATE INDEX idx_users_external_id ON users(external_id);

-- Table to store conversation sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    
    -- Contextual information for the session
    session_context JSONB, -- e.g., {'channel': 'telephony', 'initial_intent': 'symptom_check'}
    
    -- Status of the session
    status VARCHAR(50) DEFAULT 'active' -- 'active', 'completed', 'abandoned', 'escalated'
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);

-- =====================================================================
-- DIALOGUE & STATE
-- =====================================================================

-- Table to log every message in a conversation
CREATE TABLE dialogue_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actor VARCHAR(20) NOT NULL, -- 'user' or 'ai'
    
    -- Message content
    text TEXT,
    
    -- NLU / NLP processing output
    language VARCHAR(10),
    intent JSONB,
    entities JSONB,
    sentiment JSONB,
    
    -- For voice interactions
    audio_ref VARCHAR(255), -- Reference to audio file location (e.g., S3 URL)
    
    -- Metadata for turn-specific context
    metadata JSONB
);

CREATE INDEX idx_dialogue_log_session_id ON dialogue_log(session_id);
CREATE INDEX idx_dialogue_log_timestamp ON dialogue_log(timestamp);

-- Table for the state machine to persist state between turns/sessions
CREATE TABLE state_machine_data (
    session_id UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    current_state VARCHAR(100) NOT NULL,
    state_payload JSONB, -- Data associated with the current state
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================================
-- KNOWLEDGE BASE (for RAG)
-- =====================================================================

-- Table to store documents for the Retrieval-Augmented Generation system
CREATE TABLE knowledge_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Document source and content
    source_uri VARCHAR(255) UNIQUE, -- e.g., URL, file path
    document_type VARCHAR(50), -- 'pdf', 'webpage', 'text'
    content TEXT,
    
    -- Metadata
    title VARCHAR(255),
    author VARCHAR(255),
    published_date DATE,
    metadata JSONB,
    
    -- Processing status
    last_indexed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_knowledge_articles_source_uri ON knowledge_articles(source_uri);

-- Table to store text chunks from knowledge articles for vectorization
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES knowledge_articles(id) ON DELETE CASCADE,
    
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    
    -- A reference to where the vector is stored, if not in this table.
    -- If using a vector database like pgvector, you would add a `vector` column here.
    -- vector vector(1536), -- Example for pgvector
    vector_id VARCHAR(255), -- Example for external vector DB like Pinecone/Chroma
    
    UNIQUE(article_id, chunk_index)
);

CREATE INDEX idx_knowledge_chunks_article_id ON knowledge_chunks(article_id);

-- =====================================================================
-- TRIGGERS
-- =====================================================================

-- Trigger to automatically update the 'updated_at' timestamp on modification
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_column();

CREATE TRIGGER update_knowledge_articles_timestamp
    BEFORE UPDATE ON knowledge_articles
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_column();

-- =====================================================================
-- END OF SCHEMA
-- =====================================================================
