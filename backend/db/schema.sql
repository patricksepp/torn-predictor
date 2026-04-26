CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER UNIQUE NOT NULL,
    torn_name TEXT,
    torn_api_key_encrypted TEXT NOT NULL,
    api_key_status TEXT DEFAULT 'active',
    role TEXT DEFAULT 'user',
    subscription_tier TEXT DEFAULT 'free',
    subscription_end TIMESTAMPTZ,
    own_tbs BIGINT,
    own_str BIGINT, own_def BIGINT,
    own_spd BIGINT, own_dex BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER NOT NULL,
    estimated_tbs BIGINT NOT NULL,
    source_attack_id TEXT,
    level INTEGER, donordays INTEGER, age_days INTEGER,
    xantaken INTEGER, energydrinkused INTEGER,
    gymstrength INTEGER, gymspeed INTEGER,
    gymdefense INTEGER, gymdexterity INTEGER,
    attackswon INTEGER, statenhancersused INTEGER,
    refills INTEGER, nerverefills INTEGER,
    contributed_by INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE predictions_cache (
    torn_id INTEGER PRIMARY KEY,
    predicted_tbs BIGINT NOT NULL,
    predicted_str BIGINT, predicted_def BIGINT,
    predicted_spd BIGINT, predicted_dex BIGINT,
    confidence TEXT,
    method TEXT,
    model_version TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE model_versions (
    version TEXT PRIMARY KEY,
    training_samples INTEGER,
    rmse FLOAT, mape FLOAT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER NOT NULL,
    xanax_trade_id TEXT UNIQUE,
    days_granted INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_torn_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_torn_id INTEGER,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_training_torn_id ON training_data(torn_id);
CREATE INDEX idx_cache_expires ON predictions_cache(expires_at);
CREATE INDEX idx_users_torn_id ON users(torn_id);
