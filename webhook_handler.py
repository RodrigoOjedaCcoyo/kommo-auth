from fastapi import FastAPI, Request, Header, HTTPException
import json
import hashlib
import hmac
import logging
from supabase_sync import SupabaseSync
from kommo_client import KommoClient

app = FastAPI()
sync = SupabaseSync()
kommo = KommoClient()

# Configurar logging para que se vea en Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Nota: KOMMO_SECRET_KEY se usa para validar la firma de los webhooks
KOMMO_SECRET_KEY = "tu_clave_secreta_de_integracion"

@app.get("/")
async def root():
    """Endpoint de salud para que Render sepa que el espejo está encendido."""
    return {"status": "ok", "message": "Espejo Mágico de Kommo funcionando"}

@app.post("/webhook/kommo")
async def kommo_webhook(request: Request):
    """Receptor universal de eventos de Kommo."""
    try:
        # Intentar leer como JSON primero
        try:
            data = await request.json()
            logging.info(f"--- WEBHOOK JSON RECIBIDO ---")
        except:
            # Si falla, leer como Form Data (el estándar de Kommo para muchos eventos)
            form_data = await request.form()
            data = dict(form_data)
            logging.info(f"--- WEBHOOK FORM RECIBIDO ---")

        if not data:
            logging.warning("Webhook recibido sin datos")
            return {"status": "no data"}

        logging.info(f"LLAVES RECIBIDAS: {list(data.keys())}")
        found = False

        # ── Caso 1: Webhooks Globales de Kommo (Settings > Integrations > Webhooks)
        # Evento de mensaje nuevo: message[add][0][text], message[add][0][element_id]
        for key, value in data.items():
            if "[text]" in key and value:
                base = key.replace("[text]", "")
                lead_id_str = data.get(base + "[element_id]") or data.get(base + "[lead_id]")
                author_type = data.get(base + "[author][type]", "")
                author_name = data.get(base + "[author][name]", "")
                # "bot" o "user" = saliente, "contact" = entrante
                direction = "saliente" if author_type in ("bot", "user") else "entrante"

                if lead_id_str:
                    try:
                        lead_id = int(lead_id_str)
                        logging.info(f"CAPTURA -> Lead: {lead_id} [{direction}] {author_name}: {value[:60]}")
                        sync.sync_chat_analysis(lead_id, str(value), direction=direction, author=author_name)
                        found = True
                    except (ValueError, TypeError) as e:
                        logging.error(f"Error convirtiendo lead_id: {e}")

        # ── Caso 2: Pipeline Trigger (add/update de lead)  
        # Formato: leads[add][0][id], leads[status][0][id] etc.
        # Solo loggeamos para confirmar recepción; no hay texto de mensaje aquí.
        if not found:
            lead_keys = [k for k in data.keys() if "leads[" in k and "[id]" in k]
            if lead_keys:
                lead_id_str = data.get(lead_keys[0])
                logging.info(f"Evento de Lead (sin mensaje) para lead_id={lead_id_str}. OK.")

        return {"status": "success", "processed": found}

    except Exception as e:
        logging.error(f"FALLO CRÍTICO EN WEBHOOK: {str(e)}")
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
