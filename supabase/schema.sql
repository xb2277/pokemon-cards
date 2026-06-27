-- ============================================================
-- Pokemon Cards Manager - Supabase PostgreSQL Schema
-- Run this in Supabase SQL Editor (all at once)
-- ============================================================

-- ============ Extensions ============
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============ Profiles table (extends auth.users) ============
CREATE TABLE IF NOT EXISTS profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       VARCHAR(255) DEFAULT '',
    username    VARCHAR(50) DEFAULT '',
    nick_name   VARCHAR(50) DEFAULT '',
    avatar      VARCHAR(255) DEFAULT '',
    phone       VARCHAR(20) DEFAULT '',
    role        VARCHAR(10) DEFAULT 'user',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile when a user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $body$
BEGIN
    INSERT INTO public.profiles (id, email, username, nick_name, role)
    VALUES (
        NEW.id,
        COALESCE(NEW.email, ''),
        COALESCE(NEW.raw_user_meta_data->>'username', ''),
        COALESCE(NEW.raw_user_meta_data->>'nick_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'role', 'user')
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$body$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- ============ Card Catalog table ============
CREATE TABLE IF NOT EXISTS card_catalog (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    name_en         VARCHAR(100) DEFAULT '',
    set_name        VARCHAR(80) DEFAULT '',
    set_code        VARCHAR(30) DEFAULT '',
    card_number     VARCHAR(20) DEFAULT '',
    rarity          VARCHAR(20) DEFAULT '',
    image_url       VARCHAR(500) DEFAULT '',
    description     TEXT DEFAULT '',
    market_price    REAL DEFAULT 0,
    category        TEXT DEFAULT 'PTCG-SC',
    language        TEXT DEFAULT 'zh',
    tcg_id          VARCHAR(100) DEFAULT '',
    hp              INTEGER DEFAULT NULL,
    types           TEXT DEFAULT NULL,
    subtypes        TEXT DEFAULT NULL,
    evolves_from    TEXT DEFAULT NULL,
    abilities       TEXT DEFAULT NULL,
    attacks         TEXT DEFAULT NULL,
    weaknesses      TEXT DEFAULT NULL,
    retreat_cost    INTEGER DEFAULT NULL,
    artist          TEXT DEFAULT NULL,
    flavor_text     TEXT DEFAULT NULL,
    national_pokedex_numbers TEXT DEFAULT NULL,
    legalities      TEXT DEFAULT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_catalog_name ON card_catalog(name);
CREATE INDEX IF NOT EXISTS idx_catalog_set ON card_catalog(set_name);
CREATE INDEX IF NOT EXISTS idx_catalog_name_en ON card_catalog(name_en);

-- ============ Cards table (user collection) ============
CREATE TABLE IF NOT EXISTS cards (
    id              SERIAL PRIMARY KEY,
    user_id         UUID DEFAULT NULL,
    catalog_id      INTEGER DEFAULT NULL REFERENCES card_catalog(id) ON DELETE SET NULL,
    name            VARCHAR(100) NOT NULL,
    name_en         VARCHAR(100) DEFAULT '',
    set_name        VARCHAR(80) DEFAULT '',
    card_number     VARCHAR(20) DEFAULT '',
    rarity          VARCHAR(20) DEFAULT 'C',
    condition       VARCHAR(10) DEFAULT 'NM',
    quantity        INTEGER DEFAULT 1,
    cost_price      REAL DEFAULT 0,
    market_price    REAL DEFAULT 0,
    image_path      VARCHAR(500) DEFAULT '',
    tcg_id          VARCHAR(50) DEFAULT '',
    notes           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_cards_set ON cards(set_name);
CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);
CREATE INDEX IF NOT EXISTS idx_cards_catalog ON cards(catalog_id);

-- ============ Price Records table ============
CREATE TABLE IF NOT EXISTS price_records (
    id              SERIAL PRIMARY KEY,
    card_id         INTEGER DEFAULT NULL REFERENCES cards(id) ON DELETE SET NULL,
    catalog_id      INTEGER DEFAULT NULL REFERENCES card_catalog(id) ON DELETE CASCADE,
    platform        VARCHAR(30) NOT NULL,
    price           REAL NOT NULL,
    currency        VARCHAR(3) DEFAULT 'CNY',
    recorded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prices_card ON price_records(card_id);
CREATE INDEX IF NOT EXISTS idx_prices_catalog ON price_records(catalog_id);
CREATE INDEX IF NOT EXISTS idx_prices_date ON price_records(recorded_at);

-- ============ Snapshots table ============
CREATE TABLE IF NOT EXISTS snapshots (
    id              SERIAL PRIMARY KEY,
    total_value     REAL DEFAULT 0,
    total_cost      REAL DEFAULT 0,
    snapshot_date   DATE UNIQUE
);

-- ============ Pipeline Runs table ============
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    method_id       VARCHAR(50) NOT NULL,
    method_name     VARCHAR(100) DEFAULT '',
    status          VARCHAR(20) DEFAULT 'running',
    dry_run         BOOLEAN DEFAULT FALSE,
    stats           TEXT DEFAULT '{}',
    message         TEXT DEFAULT '',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pipeline_method ON pipeline_runs(method_id);

-- ============ updated_at trigger function ============
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $body$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$body$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cards_updated_at ON cards;
CREATE TRIGGER cards_updated_at BEFORE UPDATE ON cards
    FOR EACH ROW EXECUTE PROCEDURE update_timestamp();

DROP TRIGGER IF EXISTS catalog_updated_at ON card_catalog;
CREATE TRIGGER catalog_updated_at BEFORE UPDATE ON card_catalog
    FOR EACH ROW EXECUTE PROCEDURE update_timestamp();

-- ============================================================
-- Row Level Security (RLS) Policies
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE card_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;

-- Helper function: check if current user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $body$
    SELECT EXISTS (
        SELECT 1 FROM profiles
        WHERE id = auth.uid() AND role = 'admin'
    );
$body$ LANGUAGE SQL SECURITY DEFINER;

-- ---- Profiles policies ----
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id OR is_admin());

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- ---- Cards policies ----
CREATE POLICY "Users can view own cards" ON cards
    FOR SELECT USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users can insert own cards" ON cards
    FOR INSERT WITH CHECK (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users can update own cards" ON cards
    FOR UPDATE USING (auth.uid() = user_id OR is_admin());

CREATE POLICY "Users can delete own cards" ON cards
    FOR DELETE USING (auth.uid() = user_id OR is_admin());

-- ---- Card Catalog policies (read-only for regular users) ----
CREATE POLICY "Anyone can read catalog" ON card_catalog
    FOR SELECT USING (true);

CREATE POLICY "Only admin can insert catalog" ON card_catalog
    FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Only admin can update catalog" ON card_catalog
    FOR UPDATE USING (is_admin());

CREATE POLICY "Only admin can delete catalog" ON card_catalog
    FOR DELETE USING (is_admin());

-- ---- Price Records policies ----
CREATE POLICY "Anyone can read prices" ON price_records
    FOR SELECT USING (true);

CREATE POLICY "Authenticated can insert prices" ON price_records
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Only admin can delete prices" ON price_records
    FOR DELETE USING (is_admin());

-- ---- Snapshots policies ----
CREATE POLICY "Anyone can read snapshots" ON snapshots
    FOR SELECT USING (true);

CREATE POLICY "Only admin can write snapshots" ON snapshots
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- ---- Pipeline Runs policies ----
CREATE POLICY "Only admin can read pipeline runs" ON pipeline_runs
    FOR SELECT USING (is_admin());

CREATE POLICY "Only admin can write pipeline runs" ON pipeline_runs
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

-- ============ Storage bucket for card images ============
INSERT INTO storage.buckets (id, name, public)
VALUES ('card-images', 'card-images', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies: users can upload their own images
CREATE POLICY "Authenticated can upload images" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'card-images' AND auth.uid() IS NOT NULL
    );

CREATE POLICY "Anyone can read images" ON storage.objects
    FOR SELECT USING (bucket_id = 'card-images');

CREATE POLICY "Users can delete own images" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'card-images' AND auth.uid() = owner
    );
