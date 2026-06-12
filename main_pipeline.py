import logging
import pandas as pd
from kommo_client import KommoClient
from supabase_sync import SupabaseSync

# Configurar Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def run_pipeline():
    logging.info("--- Iniciando Pipeline de Sincronización Simplificado ---")
    
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

        # 3. Extraer y Sincronizar Leads (Recientes + Entrantes)
        logging.info("Extrayendo leads de Kommo...")
        df_leads = kommo.fetch_all_leads(days_back=2)
        df_unsorted = kommo.fetch_unsorted_leads()
        
        # Combinar ambos dataframes y priorizar por actividad reciente
        df_total = pd.concat([df_leads, df_unsorted], ignore_index=True) if not df_unsorted.empty else df_leads
        
        if not df_total.empty:
            logging.info(f"Sincronizando {len(df_total)} leads con Supabase...")
            sync.sync_leads(df_total)

        logging.info("--- Pipeline completado exitosamente ---")

    except Exception as e:
        logging.error(f"Error crítico en el pipeline: {e}", exc_info=True)

if __name__ == "__main__":
    run_pipeline()
