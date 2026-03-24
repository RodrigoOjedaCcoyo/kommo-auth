from fastapi import FastAPI, Request, Header, HTTPException
import hashlib
import hmac
import logging
from supabase_sync import SupabaseSync
from kommo_client import KommoClient

app = FastAPI()
sync = SupabaseSync()
kommo = KommoClient()

# Nota: KOMMO_SECRET_KEY se usa para validar la firma de los webhooks
KOMMO_SECRET_KEY = "tu_clave_secreta_de_integracion"

@app.post("/webhook/kommo")
async def kommo_webhook(request: Request, x_ca_signature: str = Header(None)):
    """Receptor de eventos en tiempo real de Kommo."""
    
    # Lectura del cuerpo
    body = await request.form()
    data = dict(body)
    
    # 1. Validación de Firma (Opcional pero recomendado)
    # Aquí iría la lógica de hmac si Kommo envía firma
    
    logging.info(f"Evento recibido: {data.get('leads[status][0][id]')}")

    # 3. Captura de mensajes de CHAT (aquí es donde llega el TEXTO real)
    logging.info(f"Full Webhook Data: {data}")
    
    # Kommo envía los chats bajo claves como 'message[add][0][text]'
    for key, value in data.items():
        if "[text]" in key:
            try:
                # Buscar el element_id o lead_id asociado en la misma estructura
                # Ej: si la clave es message[add][0][text], el ID está en message[add][0][element_id]
                id_key = key.replace("[text]", "[element_id]")
                lead_id = data.get(id_key) or data.get(key.replace("[text]", "[lead_id]"))
                
                if lead_id and value:
                    logging.info(f"Capturando chat para ID {lead_id}: {value}")
                    sync.sync_chat_analysis(int(lead_id), f"{value}")
            except Exception as e:
                logging.error(f"Error procesando mensaje de chat: {e}")

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
