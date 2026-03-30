import os
import json
import hashlib
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
        """Sincroniza leads y genera eventos de historial si hay cambios."""
        if df_leads.empty: return
        
        # 1. Obtener estados actuales de la DB para comparar (Lógica de Historial)
        ids = df_leads["id"].tolist()
        current_db_leads = self.supabase.table("leads_master").select("id, status_id, price").in_("id", ids).execute().data
        db_map = {item["id"]: item for item in current_db_leads}

        events = []
        leads_to_upsert = []

        for _, row in df_leads.iterrows():
            lead_id = row["id"]
            new_status = row["status_id"]
            new_price = row["price"]
            
            # Comparar para Historial
            if lead_id in db_map:
                old_status = db_map[lead_id]["status_id"]
                if old_status != new_status:
                    event_hash = hashlib.md5(f"{lead_id}_{old_status}_{new_status}".encode()).hexdigest()
                    events.append({
                        "lead_id": lead_id,
                        "event_type": "status_change",
                        "old_value": str(old_status),
                        "new_value": str(new_status),
                        "event_hash": event_hash
                    })
            
            leads_to_upsert.append(row.to_dict())

        # 2. Ejecutar UPSERT de Leads
        # Limpieza de valores para JSON
        for l in leads_to_upsert:
            for k, v in l.items():
                if isinstance(v, list):
                    continue
                if pd.isna(v): 
                    l[k] = None

        self.supabase.table("leads_master").upsert(leads_to_upsert).execute()
        
        # 3. Insertar Eventos (con manejo de errores por el hash único)
        if events:
            try:
                self.supabase.table("lead_events").upsert(events, on_conflict="event_hash").execute()
                logging.info(f"Registrados {len(events)} nuevos eventos de historial.")
            except Exception as e:
                logging.warning(f"Algunos eventos ya estaban registrados: {e}")

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

    def sync_chat_analysis(self, lead_id, text, direction="entrante", author=""):
        """Acumula mensajes de chat en un hilo de conversación para análisis de IA."""
        if not text: return
        import datetime
        nuevo_mensaje = {
            "time": datetime.datetime.utcnow().isoformat(),
            "from": direction,  # "entrante" o "saliente"
            "author": author,
            "text": text
        }
        try:
            # 1. Leer hilo existente
            result = self.supabase.table("chat_analysis").select("raw_messages").eq("lead_id", lead_id).execute()
            
            if result.data:
                # Existe: agregar el mensaje al hilo
                existing = result.data[0].get("raw_messages") or []
                if isinstance(existing, dict):  # compat con formato viejo
                    existing = [existing]
                existing.append(nuevo_mensaje)
                self.supabase.table("chat_analysis").update({
                    "raw_messages": existing,
                    "last_message_at": nuevo_mensaje["time"]
                }).eq("lead_id", lead_id).execute()
                logging.info(f"HILO ACTUALIZADO para lead {lead_id} ({direction}): {text[:50]}")
            else:
                # No existe: crear nuevo registro
                self.supabase.table("chat_analysis").insert({
                    "lead_id": lead_id,
                    "raw_messages": [nuevo_mensaje],
                    "last_message_at": nuevo_mensaje["time"]
                }).execute()
                logging.info(f"HILO CREADO para lead {lead_id} ({direction}): {text[:50]}")
        except Exception as e:
            logging.error(f"Error al sincronizar hilo del lead {lead_id}: {e}")

    def sync_chat_analysis_full(self, lead_id, chat_list):
        """Sincroniza un listado completo de chats en lugar de mensaje por mensaje."""
        if not chat_list: return
        
        last_msg_time = chat_list[-1]["time"]
        
        try:
            # Upsert relying on lead_id (requires lead_id to be unique/pkey or upsert logic)
            # Or just check if exists and update/insert
            result = self.supabase.table("chat_analysis").select("id").eq("lead_id", lead_id).execute()
            if result.data:
                self.supabase.table("chat_analysis").update({
                    "raw_messages": chat_list,
                    "last_message_at": last_msg_time
                }).eq("lead_id", lead_id).execute()
                logging.info(f"HILO REESCRITO COMPLETO vía API para lead {lead_id} ({len(chat_list)} mensajes)")
            else:
                self.supabase.table("chat_analysis").insert({
                    "lead_id": lead_id,
                    "raw_messages": chat_list,
                    "last_message_at": last_msg_time
                }).execute()
                logging.info(f"HILO CREADO COMPLETO vía API para lead {lead_id} ({len(chat_list)} mensajes)")
        except Exception as e:
            logging.error(f"Error al sincronizar historial completo del lead {lead_id}: {e}")


