import logging
import pandas as pd
from kommo_client import KommoClient
from supabase_sync import SupabaseSync

# Configurar Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline_telemetry.log"),
        logging.StreamHandler()
    ]
)

def run_telemetry_pipeline():
    logging.info("--- Iniciando Pipeline de Telemetría Avanzada ---")
    
    try:
        kommo = KommoClient()
        sync = SupabaseSync()

        # 1. Sincronizar Usuarios (Vendedores)
        logging.info("Sincronizando agentes...")
        users = kommo.get_users()
        sync.sync_users(users)

        # 2. Sincronizar Estadísticas Globales (Daily Snapshot)
        logging.info("Sincronizando estadísticas globales...")
        stats = kommo.get_global_stats()
        sync.sync_stats(stats)

        # 3. Extraer y Sincronizar Leads (Últimas 48 horas para asegurar todos los recientes)
        logging.info("Extrayendo leads con historial y chats...")
        df_leads = kommo.fetch_all_leads(days_back=2)
        
        if not df_leads.empty:
            # Sincronizar Leads y Eventos de Historial
            sync.sync_leads(df_leads)
            
            # 4. Extraer Chat History para cada Lead (Aumentado a 500 para mayor cobertura)
            logging.info("Extrayendo historiales de chat para análisis de IA...")
            for idx, lead_id in enumerate(df_leads["id"].head(500)):
                messages = kommo.get_lead_chats(lead_id)
                if messages:
                    sync.sync_chat_analysis(lead_id, messages)
                if idx % 50 == 0: logging.info(f"Procesando chats: {idx} completados.")

        logging.info("--- Pipeline de Telemetría completado exitosamente ---")

    except Exception as e:
        logging.error(f"Error crítico en el pipeline: {e}", exc_info=True)

if __name__ == "__main__":
    run_telemetry_pipeline()
