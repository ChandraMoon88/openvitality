-- =====================================================================
-- OpenVitality AI - PostgreSQL API Management Database Schema
-- =====================================================================
-- This schema stores all API configurations and enables dynamic
-- API selection, health monitoring, and automatic failover
-- =====================================================================

-- Enable UUID extension for generating unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_cron for scheduled tasks (health checks, cleanup)
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- =====================================================================
-- CORE API REGISTRY
-- =====================================================================

-- Main table storing all API configurations
CREATE TABLE api_registry (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Basic Information
    api_key VARCHAR(100) UNIQUE NOT NULL,  -- e.g., 'groq_whisper', 'edge_tts'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    provider VARCHAR(100),  -- e.g., 'Groq', 'Microsoft', 'Google'
    
    -- API Category - what type of service this provides
    category VARCHAR(50) NOT NULL,  -- 'stt', 'tts', 'llm', 'translation', 'medical_knowledge', etc.
    subcategory VARCHAR(50),  -- For finer classification
    
    -- Connection Details
    base_url TEXT NOT NULL,
    documentation_url TEXT,
    
    -- Authentication
    auth_type VARCHAR(50) DEFAULT 'none',  -- 'none', 'api_key', 'bearer', 'oauth2', 'basic'
    auth_key_name VARCHAR(100),  -- e.g., 'X-API-Key', 'Authorization'
    requires_auth BOOLEAN DEFAULT false,
    
    -- Rate Limiting (from API provider)
    rate_limit_per_second INTEGER,
    rate_limit_per_minute INTEGER,
    rate_limit_per_hour INTEGER,
    rate_limit_per_day INTEGER,
    rate_limit_per_month INTEGER,
    
    -- Cost Information
    cost_type VARCHAR(50) DEFAULT 'free',  -- 'free', 'freemium', 'paid'
    free_tier_limit TEXT,  -- Description of free tier limits
    
    -- Quality & Performance Characteristics
    quality_score DECIMAL(3,2) DEFAULT 0.0,  -- 0.0 to 1.0 based on performance
    average_latency_ms INTEGER,  -- Average response time
    
    -- Availability & Reliability
    is_active BOOLEAN DEFAULT true,
    is_healthy BOOLEAN DEFAULT true,
    last_health_check TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    
    -- Priority & Fallback Configuration
    priority INTEGER DEFAULT 100,  -- Lower number = higher priority
    is_fallback BOOLEAN DEFAULT false,
    fallback_for UUID REFERENCES api_registry(id),  -- Which API is this a backup for?
    
    -- Supported Features (stored as JSON for flexibility)
    supported_languages TEXT[],  -- Array of language codes
    supported_formats TEXT[],  -- e.g., ['json', 'xml', 'wav', 'mp3']
    capabilities JSONB,  -- Additional capabilities as key-value pairs
    
    -- Regional Configuration
    available_regions TEXT[],  -- e.g., ['us-east-1', 'eu-west-1', 'ap-south-1']
    compliance_standards TEXT[],  -- e.g., ['HIPAA', 'GDPR', 'DPDP']
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system',
    notes TEXT
);

-- Indexes for fast lookups
CREATE INDEX idx_api_category ON api_registry(category);
CREATE INDEX idx_api_active_healthy ON api_registry(is_active, is_healthy);
CREATE INDEX idx_api_priority ON api_registry(priority);
CREATE INDEX idx_api_key ON api_registry(api_key);

-- =====================================================================
-- API ENDPOINTS
-- =====================================================================

-- Store specific endpoints for each API
CREATE TABLE api_endpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id) ON DELETE CASCADE,
    
    endpoint_name VARCHAR(100) NOT NULL,  -- e.g., 'search', 'transcribe', 'generate'
    endpoint_path TEXT NOT NULL,  -- e.g., '/v1/audio/transcriptions'
    http_method VARCHAR(10) DEFAULT 'POST',  -- GET, POST, PUT, DELETE
    
    -- Request Configuration
    request_content_type VARCHAR(100),  -- e.g., 'application/json', 'multipart/form-data'
    required_parameters JSONB,  -- JSON object defining required params
    optional_parameters JSONB,
    
    -- Response Configuration
    response_format VARCHAR(50),  -- 'json', 'xml', 'binary'
    response_schema JSONB,  -- Expected response structure
    
    -- Rate Limits specific to this endpoint
    rate_limit_override JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(api_id, endpoint_name)
);

CREATE INDEX idx_endpoint_api ON api_endpoints(api_id);

-- =====================================================================
-- API CREDENTIALS (Encrypted)
-- =====================================================================

-- Securely store API keys and secrets
CREATE TABLE api_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id) ON DELETE CASCADE,
    
    credential_name VARCHAR(100) NOT NULL,  -- 'primary_key', 'client_id', 'client_secret'
    credential_value TEXT NOT NULL,  -- Encrypted API key
    
    -- Key Rotation
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP,
    last_used TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    notes TEXT,
    
    UNIQUE(api_id, credential_name)
);

CREATE INDEX idx_credentials_api ON api_credentials(api_id);

-- =====================================================================
-- API USAGE TRACKING
-- =====================================================================

-- Track every API call for monitoring and billing
CREATE TABLE api_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id),
    endpoint_name VARCHAR(100),
    
    -- Request Details
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    request_id VARCHAR(100),  -- For tracing across systems
    session_id VARCHAR(100),  -- User session
    
    -- Performance Metrics
    response_time_ms INTEGER,
    status_code INTEGER,
    success BOOLEAN,
    
    -- Error Tracking
    error_type VARCHAR(100),
    error_message TEXT,
    
    -- Cost Tracking
    tokens_used INTEGER,
    estimated_cost DECIMAL(10,6),
    
    -- Context (for analytics)
    user_country VARCHAR(5),
    use_case VARCHAR(100),
    
    CONSTRAINT chk_status_code CHECK (status_code >= 100 AND status_code < 600)
);

-- Partition by month for performance (optional but recommended)
-- CREATE TABLE api_usage_log_2025_01 PARTITION OF api_usage_log
--     FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE INDEX idx_usage_api_timestamp ON api_usage_log(api_id, request_timestamp DESC);
CREATE INDEX idx_usage_session ON api_usage_log(session_id);
CREATE INDEX idx_usage_timestamp ON api_usage_log(request_timestamp DESC);

-- =====================================================================
-- API HEALTH STATUS
-- =====================================================================

-- Store health check results
CREATE TABLE api_health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id) ON DELETE CASCADE,
    
    check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_healthy BOOLEAN,
    
    -- Health Metrics
    response_time_ms INTEGER,
    status_code INTEGER,
    error_message TEXT,
    
    -- Detailed Status
    endpoint_tested TEXT,
    test_payload JSONB,
    test_response JSONB
);

CREATE INDEX idx_health_api_timestamp ON api_health_checks(api_id, check_timestamp DESC);

-- =====================================================================
-- API RATE LIMIT TRACKING
-- =====================================================================

-- Track rate limit consumption in real-time
CREATE TABLE api_rate_limits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id) ON DELETE CASCADE,
    credential_id UUID REFERENCES api_credentials(id),
    
    -- Time Window
    window_start TIMESTAMP NOT NULL,
    window_duration INTERVAL NOT NULL,  -- '1 second', '1 minute', '1 hour', '1 day'
    
    -- Usage Counters
    request_count INTEGER DEFAULT 0,
    request_limit INTEGER,
    
    -- Token Counters (for LLMs)
    tokens_used INTEGER DEFAULT 0,
    tokens_limit INTEGER,
    
    -- Status
    limit_reached BOOLEAN DEFAULT false,
    resets_at TIMESTAMP,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(api_id, credential_id, window_start, window_duration)
);

CREATE INDEX idx_rate_limits_api ON api_rate_limits(api_id, window_start DESC);

-- =====================================================================
-- API SELECTION RULES
-- =====================================================================

-- Define intelligent routing rules
CREATE TABLE api_selection_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    rule_name VARCHAR(100) UNIQUE NOT NULL,
    rule_description TEXT,
    
    -- Matching Criteria
    category VARCHAR(50),  -- Which category this rule applies to
    conditions JSONB,  -- Complex conditions as JSON
    
    -- Selection Logic
    preferred_api_ids UUID[],  -- Ordered list of API IDs to try
    selection_strategy VARCHAR(50) DEFAULT 'priority',  -- 'priority', 'round_robin', 'least_latency', 'random'
    
    -- Rule Priority
    priority INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- API BLACKOUTS / MAINTENANCE WINDOWS
-- =====================================================================

-- Schedule known maintenance windows
CREATE TABLE api_maintenance_windows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_id UUID REFERENCES api_registry(id) ON DELETE CASCADE,
    
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    
    reason TEXT,
    planned BOOLEAN DEFAULT true,  -- true = scheduled, false = unexpected outage
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_maintenance_times CHECK (end_time > start_time)
);

CREATE INDEX idx_maintenance_api_time ON api_maintenance_windows(api_id, start_time, end_time);

-- =====================================================================
-- VIEWS FOR EASY QUERYING
-- =====================================================================

-- View: Healthy APIs by Category
CREATE VIEW v_healthy_apis AS
SELECT 
    ar.id,
    ar.api_key,
    ar.name,
    ar.category,
    ar.subcategory,
    ar.base_url,
    ar.priority,
    ar.quality_score,
    ar.average_latency_ms,
    ar.supported_languages
FROM api_registry ar
WHERE ar.is_active = true 
  AND ar.is_healthy = true
  AND ar.consecutive_failures < 3
ORDER BY ar.category, ar.priority;

-- View: API Usage Statistics (Last 24 Hours)
CREATE VIEW v_api_usage_24h AS
SELECT 
    ar.api_key,
    ar.name,
    ar.category,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE aul.success = true) as successful_requests,
    COUNT(*) FILTER (WHERE aul.success = false) as failed_requests,
    ROUND(AVG(aul.response_time_ms)::numeric, 2) as avg_response_time_ms,
    ROUND((COUNT(*) FILTER (WHERE aul.success = true)::numeric / NULLIF(COUNT(*), 0) * 100), 2) as success_rate_pct
FROM api_registry ar
LEFT JOIN api_usage_log aul ON ar.id = aul.api_id
WHERE aul.request_timestamp > NOW() - INTERVAL '24 hours'
GROUP BY ar.id, ar.api_key, ar.name, ar.category
ORDER BY total_requests DESC;

-- View: Current Rate Limit Status
CREATE VIEW v_current_rate_limits AS
SELECT 
    ar.api_key,
    ar.name,
    arl.window_duration,
    arl.request_count,
    arl.request_limit,
    arl.limit_reached,
    arl.resets_at,
    ROUND((arl.request_count::numeric / NULLIF(arl.request_limit, 0) * 100), 2) as usage_percentage
FROM api_registry ar
JOIN api_rate_limits arl ON ar.id = arl.api_id
WHERE arl.window_start = (
    SELECT MAX(window_start) 
    FROM api_rate_limits 
    WHERE api_id = ar.id
);

-- =====================================================================
-- FUNCTIONS & STORED PROCEDURES
-- =====================================================================

-- Function: Get best available API for a category
CREATE OR REPLACE FUNCTION get_best_api(
    p_category VARCHAR(50),
    p_language VARCHAR(10) DEFAULT NULL,
    p_region VARCHAR(50) DEFAULT NULL
)
RETURNS TABLE (
    api_id UUID,
    api_key VARCHAR(100),
    name VARCHAR(255),
    base_url TEXT,
    priority INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ar.id,
        ar.api_key,
        ar.name,
        ar.base_url,
        ar.priority
    FROM api_registry ar
    WHERE ar.category = p_category
      AND ar.is_active = true
      AND ar.is_healthy = true
      AND ar.consecutive_failures < 3
      AND (p_language IS NULL OR p_language = ANY(ar.supported_languages))
      AND (p_region IS NULL OR p_region = ANY(ar.available_regions))
      -- Check if not in maintenance window
      AND NOT EXISTS (
          SELECT 1 FROM api_maintenance_windows amw
          WHERE amw.api_id = ar.id
            AND NOW() BETWEEN amw.start_time AND amw.end_time
      )
      -- Check if not rate limited
      AND NOT EXISTS (
          SELECT 1 FROM api_rate_limits arl
          WHERE arl.api_id = ar.id
            AND arl.limit_reached = true
            AND NOW() < arl.resets_at
      )
    ORDER BY ar.priority ASC, ar.quality_score DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function: Record API usage
CREATE OR REPLACE FUNCTION record_api_usage(
    p_api_id UUID,
    p_endpoint_name VARCHAR(100),
    p_response_time_ms INTEGER,
    p_success BOOLEAN,
    p_status_code INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL,
    p_session_id VARCHAR(100) DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO api_usage_log (
        api_id,
        endpoint_name,
        response_time_ms,
        success,
        status_code,
        error_message,
        session_id
    ) VALUES (
        p_api_id,
        p_endpoint_name,
        p_response_time_ms,
        p_success,
        p_status_code,
        p_error_message,
        p_session_id
    ) RETURNING id INTO v_log_id;
    
    -- Update API health based on result
    IF NOT p_success THEN
        UPDATE api_registry
        SET consecutive_failures = consecutive_failures + 1,
            is_healthy = CASE WHEN consecutive_failures + 1 >= 5 THEN false ELSE is_healthy END
        WHERE id = p_api_id;
    ELSE
        UPDATE api_registry
        SET consecutive_failures = 0,
            is_healthy = true,
            average_latency_ms = (COALESCE(average_latency_ms, 0) * 0.9 + p_response_time_ms * 0.1)::INTEGER
        WHERE id = p_api_id;
    END IF;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Increment rate limit counter
CREATE OR REPLACE FUNCTION increment_rate_limit(
    p_api_id UUID,
    p_window_duration INTERVAL DEFAULT '1 minute'::INTERVAL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_window_start TIMESTAMP;
    v_request_limit INTEGER;
    v_current_count INTEGER;
BEGIN
    -- Calculate window start based on duration
    v_window_start := DATE_TRUNC('minute', NOW());
    
    -- Get the rate limit for this window
    SELECT CASE 
        WHEN p_window_duration = '1 second'::INTERVAL THEN rate_limit_per_second
        WHEN p_window_duration = '1 minute'::INTERVAL THEN rate_limit_per_minute
        WHEN p_window_duration = '1 hour'::INTERVAL THEN rate_limit_per_hour
        WHEN p_window_duration = '1 day'::INTERVAL THEN rate_limit_per_day
        ELSE NULL
    END INTO v_request_limit
    FROM api_registry WHERE id = p_api_id;
    
    -- If no limit defined, allow the request
    IF v_request_limit IS NULL THEN
        RETURN true;
    END IF;
    
    -- Insert or update rate limit record
    INSERT INTO api_rate_limits (api_id, window_start, window_duration, request_count, request_limit, resets_at)
    VALUES (
        p_api_id, 
        v_window_start, 
        p_window_duration, 
        1, 
        v_request_limit,
        v_window_start + p_window_duration
    )
    ON CONFLICT (api_id, credential_id, window_start, window_duration) 
    DO UPDATE SET 
        request_count = api_rate_limits.request_count + 1,
        limit_reached = (api_rate_limits.request_count + 1) >= api_rate_limits.request_limit,
        updated_at = NOW();
    
    -- Get current count
    SELECT request_count INTO v_current_count
    FROM api_rate_limits
    WHERE api_id = p_api_id 
      AND window_start = v_window_start
      AND window_duration = p_window_duration;
    
    -- Return true if under limit, false if over
    RETURN v_current_count <= v_request_limit;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- TRIGGERS
-- =====================================================================

-- Trigger: Update timestamp on record modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_api_registry_updated_at 
    BEFORE UPDATE ON api_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_selection_rules_updated_at 
    BEFORE UPDATE ON api_selection_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================
-- COMMENTS FOR DOCUMENTATION
-- =====================================================================

COMMENT ON TABLE api_registry IS 'Central registry of all APIs available to the system';
COMMENT ON TABLE api_endpoints IS 'Specific endpoints for each API';
COMMENT ON TABLE api_credentials IS 'Encrypted storage for API keys and secrets';
COMMENT ON TABLE api_usage_log IS 'Historical log of all API calls for monitoring and analytics';
COMMENT ON TABLE api_health_checks IS 'Results of automated health checks';
COMMENT ON TABLE api_rate_limits IS 'Real-time tracking of rate limit consumption';
COMMENT ON TABLE api_selection_rules IS 'Rules for intelligent API selection based on context';
COMMENT ON TABLE api_maintenance_windows IS 'Scheduled and unplanned maintenance windows';

COMMENT ON FUNCTION get_best_api IS 'Returns the best available API for a given category, considering health, rate limits, and priorities';
COMMENT ON FUNCTION record_api_usage IS 'Records an API call and updates health metrics';
COMMENT ON FUNCTION increment_rate_limit IS 'Increments rate limit counter and returns whether the request is allowed';

-- =====================================================================
-- END OF SCHEMA
-- =====================================================================