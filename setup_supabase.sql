-- Script de Reinicio y Creación de Esquema (Kommo -> Supabase)
-- ¡ATENCIÓN!: Esto borrará todos los datos actuales en las tablas mencionadas.

DROP TABLE IF EXISTS public.itineraries_sync;
DROP TABLE IF EXISTS public.chat_analysis;
DROP TABLE IF EXISTS public.lead_events;
DROP TABLE IF EXISTS public.leads_master;
DROP TABLE IF EXISTS public.users_master;
DROP TABLE IF EXISTS public.kommo_analytics_snapshots;
DROP TABLE IF EXISTS public.kommo_oauth_tokens;

-- 1. Maestría de Agentes (Vendedores)
CREATE TABLE IF NOT EXISTS public.users_master (
    id BIGINT PRIMARY KEY,
    name TEXT,
    email TEXT,
    is_active BOOLEAN,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Maestría de Leads (Estado Actual y Atribución)
CREATE TABLE IF NOT EXISTS public.leads_master (
    id BIGINT PRIMARY KEY,
    name TEXT,
    price INTEGER,
    status_id INTEGER,
    pipeline_id INTEGER,
    responsible_user_id BIGINT REFERENCES public.users_master(id),
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    
    -- Variables de Marketing críticas para MMM
    gclid TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_content TEXT,
    utm_term TEXT,
    fbc TEXT,
    fbp TEXT,
    marketing_channel TEXT, -- Normalizado (Meta_Ads, Google_Ads, etc.)
    
    -- Rentabilidad
    total_cost_itinerary NUMERIC(10,2),
    offered_price_itinerary NUMERIC(10,2),
    
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Historial de Eventos (Con Idempotencia)
CREATE TABLE IF NOT EXISTS public.lead_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lead_id BIGINT REFERENCES public.leads_master(id),
    event_type TEXT, -- 'status_change', 'price_change', 'note_added'
    old_value TEXT,
    new_value TEXT,
    event_hash TEXT UNIQUE, -- Para evitar duplicados de Webhooks
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Historial de Chats (Para análisis de IA)
CREATE TABLE IF NOT EXISTS public.chat_analysis (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lead_id BIGINT REFERENCES public.leads_master(id),
    raw_messages JSONB,
    ia_score_intent NUMERIC(3,2),
    ia_objections JSONB,
    last_message_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- 5. Analítica Nativa de Kommo (Snapshots Agregados)
CREATE TABLE IF NOT EXISTS public.kommo_analytics_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date DATE DEFAULT CURRENT_DATE,
    leads_count INTEGER,
    converted_leads INTEGER,
    lost_leads INTEGER,
    average_closing_time NUMERIC(10,2), -- En segundos
    revenue NUMERIC(12,2),
    raw_stats_json JSONB
);

-- 6. Registro de Itinerarios
CREATE TABLE IF NOT EXISTS public.itineraries_sync (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lead_id BIGINT REFERENCES public.leads_master(id),
    version_number TEXT,
    total_cost NUMERIC(10,2),
    offered_price NUMERIC(10,2),
    items_included JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. Persistencia de Autenticación (Para GitHub Actions)
CREATE TABLE IF NOT EXISTS public.kommo_oauth_tokens (
    id INTEGER PRIMARY KEY DEFAULT 1,
    access_token TEXT,
    refresh_token TEXT,
    expires_at BIGINT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT one_row_only CHECK (id = 1) -- Solo permitimos una fila de tokens
);

-- Índices y Seguridad
CREATE INDEX IF NOT EXISTS idx_leads_marketing_channel ON public.leads_master(marketing_channel);
CREATE INDEX IF NOT EXISTS idx_leads_responsible ON public.leads_master(responsible_user_id);
CREATE INDEX IF NOT EXISTS idx_stats_date ON public.kommo_analytics_snapshots(snapshot_date);
