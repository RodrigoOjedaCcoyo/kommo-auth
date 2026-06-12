-- Script de Reinicio y Creación de Esquema Simplificado (Kommo -> Supabase)
-- ¡ATENCIÓN!: Esto borrará todos los datos actuales en las tablas mencionadas.

DROP TABLE IF EXISTS public.leads_master;
DROP TABLE IF EXISTS public.users_master;
DROP TABLE IF EXISTS public.kommo_analytics_snapshots;
DROP TABLE IF EXISTS public.kommo_oauth_tokens;
-- Las tablas de IA, webhooks y chats han sido eliminadas.

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
    tags JSONB, -- Etiquetas asignadas en Kommo
    
    -- Rentabilidad
    total_cost_itinerary NUMERIC(10,2),
    offered_price_itinerary NUMERIC(10,2),
    
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Analítica Nativa de Kommo (Snapshots Agregados)
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

-- 4. Persistencia de Autenticación
CREATE TABLE IF NOT EXISTS public.kommo_oauth_tokens (
    id INTEGER PRIMARY KEY DEFAULT 1,
    access_token TEXT,
    refresh_token TEXT,
    expires_at BIGINT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT one_row_only CHECK (id = 1)
);

-- Índices y Seguridad
CREATE INDEX IF NOT EXISTS idx_leads_marketing_channel ON public.leads_master(marketing_channel);
CREATE INDEX IF NOT EXISTS idx_leads_responsible ON public.leads_master(responsible_user_id);
