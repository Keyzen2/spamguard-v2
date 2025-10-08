-- =====================================================
-- MIGRATION 006: Multi-Tenant & API SaaS
-- =====================================================

-- Tabla de usuarios/clientes (API users)
CREATE TABLE IF NOT EXISTS api_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    company_name VARCHAR(255),
    
    -- Plan info
    plan VARCHAR(50) DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- Tabla de API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES api_users(id) ON DELETE CASCADE,
    
    -- Key info
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL, -- sg_live_ o sg_test_
    name VARCHAR(255), -- Nombre descriptivo
    
    -- Permissions
    scopes TEXT[] DEFAULT ARRAY['analyze', 'feedback', 'stats'],
    
    -- Rate limiting
    rate_limit_tier VARCHAR(50) DEFAULT 'free',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Usage tracking
    last_used_at TIMESTAMP,
    total_requests INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Índices para API keys
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);

-- Tabla de uso mensual (billing)
CREATE TABLE IF NOT EXISTS monthly_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES api_users(id) ON DELETE CASCADE,
    
    -- Period
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    
    -- Usage
    requests_count INTEGER DEFAULT 0,
    analyze_requests INTEGER DEFAULT 0,
    feedback_requests INTEGER DEFAULT 0,
    
    -- Costs
    plan VARCHAR(50),
    amount_charged DECIMAL(10, 2),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(user_id, year, month)
);

CREATE INDEX idx_monthly_usage_user_period ON monthly_usage(user_id, year, month);

-- Tabla de requests (logs detallados)
CREATE TABLE IF NOT EXISTS api_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    
    -- Request info
    endpoint VARCHAR(255),
    method VARCHAR(10),
    
    -- Input
    text_length INTEGER,
    context JSONB,
    
    -- Output
    prediction JSONB, -- {category, confidence, scores}
    processing_time_ms INTEGER,
    
    -- Meta
    ip_address INET,
    user_agent TEXT,
    
    -- Status
    status_code INTEGER,
    error_message TEXT,
    
    -- Timestamp
    created_at TIMESTAMP DEFAULT NOW()
);

-- Particionado por fecha (optimización para grandes volúmenes)
CREATE INDEX idx_api_requests_user_id ON api_requests(user_id);
CREATE INDEX idx_api_requests_created_at ON api_requests(created_at DESC);
CREATE INDEX idx_api_requests_api_key_id ON api_requests(api_key_id);

-- Tabla de webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES api_users(id) ON DELETE CASCADE,
    
    -- Webhook config
    url TEXT NOT NULL,
    events TEXT[] DEFAULT ARRAY['spam_detected', 'phishing_detected'],
    secret VARCHAR(255), -- Para firmar payloads
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Stats
    last_triggered_at TIMESTAMP,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabla de feedback mejorada (ya existía, añadir user_id)
ALTER TABLE feedback_queue 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES api_users(id);

-- Función para tracking de uso
CREATE OR REPLACE FUNCTION track_api_request(
    p_user_id UUID,
    p_api_key_id UUID,
    p_endpoint VARCHAR
) RETURNS VOID AS $$
BEGIN
    -- Incrementar contador mensual
    INSERT INTO monthly_usage (user_id, year, month, requests_count, analyze_requests)
    VALUES (
        p_user_id,
        EXTRACT(YEAR FROM NOW()),
        EXTRACT(MONTH FROM NOW()),
        1,
        CASE WHEN p_endpoint LIKE '%analyze%' THEN 1 ELSE 0 END
    )
    ON CONFLICT (user_id, year, month)
    DO UPDATE SET
        requests_count = monthly_usage.requests_count + 1,
        analyze_requests = monthly_usage.analyze_requests + CASE WHEN p_endpoint LIKE '%analyze%' THEN 1 ELSE 0 END;
    
    -- Actualizar last_used en API key
    UPDATE api_keys
    SET last_used_at = NOW(),
        total_requests = total_requests + 1
    WHERE id = p_api_key_id;
END;
$$ LANGUAGE plpgsql;

-- Función para verificar límite de plan
CREATE OR REPLACE FUNCTION check_rate_limit(
    p_user_id UUID,
    p_plan VARCHAR
) RETURNS BOOLEAN AS $$
DECLARE
    v_requests_count INTEGER;
    v_limit INTEGER;
BEGIN
    -- Obtener uso del mes actual
    SELECT COALESCE(requests_count, 0) INTO v_requests_count
    FROM monthly_usage
    WHERE user_id = p_user_id
      AND year = EXTRACT(YEAR FROM NOW())
      AND month = EXTRACT(MONTH FROM NOW());
    
    -- Determinar límite según plan
    v_limit := CASE p_plan
        WHEN 'free' THEN 500
        WHEN 'pro' THEN 10000
        WHEN 'business' THEN 100000
        ELSE 999999999 -- enterprise
    END;
    
    RETURN v_requests_count < v_limit;
END;
$$ LANGUAGE plpgsql;

-- Vista para dashboard de usuario
CREATE OR REPLACE VIEW user_dashboard_stats AS
SELECT 
    u.id as user_id,
    u.email,
    u.plan,
    mu.requests_count as current_month_requests,
    CASE u.plan
        WHEN 'free' THEN 500
        WHEN 'pro' THEN 10000
        WHEN 'business' THEN 100000
        ELSE 999999999
    END as monthly_limit,
    COUNT(DISTINCT ak.id) as active_api_keys,
    u.created_at as member_since
FROM api_users u
LEFT JOIN monthly_usage mu ON u.id = mu.user_id 
    AND mu.year = EXTRACT(YEAR FROM NOW())
    AND mu.month = EXTRACT(MONTH FROM NOW())
LEFT JOIN api_keys ak ON u.id = ak.user_id AND ak.is_active = true
GROUP BY u.id, u.email, u.plan, mu.requests_count, u.created_at;

-- RLS Policies
ALTER TABLE api_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_requests ENABLE ROW LEVEL SECURITY;

-- Los usuarios solo ven sus propios datos
CREATE POLICY "Users can view own data" ON api_users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can view own API keys" ON api_keys
    FOR SELECT USING (user_id IN (SELECT id FROM api_users WHERE auth.uid() = id));

CREATE POLICY "Users can view own usage" ON monthly_usage
    FOR SELECT USING (user_id IN (SELECT id FROM api_users WHERE auth.uid() = id));

CREATE POLICY "Users can view own requests" ON api_requests
    FOR SELECT USING (user_id IN (SELECT id FROM api_users WHERE auth.uid() = id));

-- Datos de ejemplo (SOLO PARA DESARROLLO)
-- COMENTAR O ELIMINAR EN PRODUCCIÓN
INSERT INTO api_users (email, plan, is_active, email_verified)
VALUES 
    ('demo@spamguard.ai', 'pro', true, true),
    ('test@example.com', 'free', true, true)
ON CONFLICT (email) DO NOTHING;
