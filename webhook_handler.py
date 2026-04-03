# v1.1.0 - Rescatando el servidor del 404 y habilitando el radar de Talk IDs
from fastapi import FastAPI, Request, Header, HTTPException
import json
import requests
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

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """Endpoint de salud para que Render sepa que el espejo está encendido."""
    return {"status": "ok", "message": "Espejo Mágico de Kommo funcionando"}

@app.get("/debug_raw/{lead_id}")
async def debug_raw(lead_id: int):
    """Muestra los datos crudos que Kommo le da al servidor sin procesar."""
    try:
        headers = kommo._get_headers()
        # 1. Datos del Lead y Contactos vinculados
        lead_resp = requests.get(f"{kommo.base_url}/leads/{lead_id}?with=contacts", headers=headers)
        lead_data = lead_resp.json() if lead_resp.status_code == 200 else {}
        
        contact_id = None
        if "_embedded" in lead_data and "contacts" in lead_data["_embedded"]:
            contact_id = lead_data["_embedded"]["contacts"][0]["id"]

        # 2. Eventos del Lead y del Contacto
        events_lead = requests.get(f"{kommo.base_url}/events", headers=headers, params={"filter[entity_id][]": [lead_id], "filter[entity]": "lead"})
        
        events_contact = {"message": "No contact found"}
        if contact_id:
            events_contact_resp = requests.get(f"{kommo.base_url}/events", headers=headers, params={"filter[entity_id][]": [contact_id], "filter[entity]": "contact"})
            events_contact = events_contact_resp.json() if events_contact_resp.status_code == 200 else f"Error {events_contact_resp.status_code}"

        # 3. Notas
        notes_lead_resp = requests.get(f"{kommo.base_url}/leads/{lead_id}/notes", headers=headers)
        
        return {
            "lead_id": lead_id,
            "contact_id_found": contact_id,
            "events_lead": events_lead.json() if events_lead.status_code == 200 else f"Error {events_lead.status_code}",
            "events_contact": events_contact,
            "notes_lead_status": notes_lead_resp.status_code,
            "notes_lead": notes_lead_resp.json() if notes_lead_resp.status_code == 200 else []
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/debug_scan/{lead_id}")
async def debug_scan(lead_id: int):
    """Túnel de diagnóstico para ver qué está capturando el extractor."""
    try:
        logging.info(f"🔍 DEBUG_SCAN manual para Lead: {lead_id}")
        history = kommo.get_lead_chats_json(lead_id)
        return {
            "lead_id": lead_id,
            "mensajes_encontrados": len(history),
            "historial": history
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
            logging.warning("--- WEBHOOK VACÍO O SIN LLAVES ---")
            return {"status": "no data"}

        logging.info(f"--- WEBHOOK RECIBIDO ---")
        logging.info(f"DATOS CRUDOS: {json.dumps(data)[:200]}...")
        logging.info(f"LLAVES: {list(data.keys())}")
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

        # ── Caso 1.5: Actualización de Conversación (talk[update])
        talk_keys = [k for k in data.keys() if "talk[update]" in k and "[entity_id]" in k]
        if talk_keys:
            lead_id_str = data.get(talk_keys[0])
            # Extraer AMBOS IDs: el corto y el largo (UUID)
            base_talk = talk_keys[0].split("[entity_id]")[0]
            talk_id_val = data.get(base_talk + "[talk_id]")
            chat_id_uuid = data.get(base_talk + "[chat_id]") # El ID largo
            
            if lead_id_str:
                try:
                    lead_id = int(lead_id_str)
                    logging.info(f"CAPTURA -> Re-sincronizando (Talk: {talk_id_val}, Chat: {chat_id_uuid}) en lead {lead_id}")
                    
                    # Intentamos traer historial, pasando el UUID como opción B
                    history = kommo.get_lead_chats_json(lead_id, talk_id_direct=talk_id_val, chat_uuid=chat_id_uuid)
                    if history:
                        sync.sync_chat_analysis_full(lead_id, history)
                        found = True
                    else:
                        logging.warning(f"API no devolvió historial (404/Vacío) para lead {lead_id}. Manteniendo captura de Webhook.")
                except Exception as e:
                    logging.error(f"Error procesando talk[update]: {e}")

        # ── Caso 2: Pipeline Trigger (add/update de lead)  
        # Formato: leads[add][0][id], leads[status][0][id] etc.
        if not found:
            lead_keys = [k for k in data.keys() if "leads[" in k and "[id]" in k]
            if lead_keys:
                lead_id_str = data.get(lead_keys[0])
                logging.info(f"Evento de Lead (sin mensaje) para lead_id={lead_id_str}. OK.")

        return {"status": "success", "processed": found}

    except Exception as e:
        logging.error(f"FALLO CRÍTICO EN WEBHOOK: {str(e)}")
        return {"status": "error", "detail": str(e)}



import os

if __name__ == "__main__":
    import uvicorn
    # En Render, PORT es la variable sagrada.
    render_port = os.environ.get("PORT")
    port = int(render_port) if render_port else 10000
    
    logging.info(f"--- INICIO DE SISTEMA ---")
    logging.info(f"Puerto detectado: {port}")
    if not render_port:
        logging.warning("⚠️ Variable PORT no detectada, usando fallback 10000")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
