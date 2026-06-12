import os
import json
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd

load_dotenv()

class SupabaseSync:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise Exception("Credenciales de Supabase no encontradas.")
        self.supabase: Client = create_client(self.url, self.key)

    def sync_users(self, users):
        """Sincroniza la tabla de agentes."""
        if not users: return
        records = []
        for u in users:
            records.append({
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "is_active": not u.get("is_free", False)
            })
        self.supabase.table("users_master").upsert(records).execute()
        logging.info(f"Sincronizados {len(records)} agentes.")

    def sync_leads(self, df_leads):
        """Sincroniza leads en estado actual (Snapshot)."""
        if df_leads.empty: return
        
        leads_to_upsert = []

        for _, row in df_leads.iterrows():
            leads_to_upsert.append(row.to_dict())

        # Limpieza de valores para JSON
        for l in leads_to_upsert:
            for k, v in l.items():
                if isinstance(v, list):
                    continue
                if pd.isna(v): 
                    l[k] = None

        self.supabase.table("leads_master").upsert(leads_to_upsert).execute()
        logging.info(f"Sincronizados {len(leads_to_upsert)} leads correctamente.")

    def sync_stats(self, stats_json):
        """Guarda un snapshot de las estadísticas globales."""
        if not stats_json: return
        data = {
            "leads_count": stats_json.get("leads", {}).get("total_count"),
            "revenue": stats_json.get("leads", {}).get("total_revenue"),
            "raw_stats_json": stats_json
        }
        self.supabase.table("kommo_analytics_snapshots").insert(data).execute()
        logging.info("Snapshot de estadísticas guardado.")
