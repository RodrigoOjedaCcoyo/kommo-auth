import time
import requests
import pandas as pd
import logging
from datetime import datetime, timezone
from auth_manager import KommoAuth

class KommoClient:
    def __init__(self):
        self.auth = KommoAuth()
        self.subdomain = self.auth.subdomain
        self.base_url = f"https://{self.subdomain}.kommo.com/api/v4"
        self.rate_limit_delay = 0.5 # Segundos de espera entre peticiones de paginación

    def _get_headers(self):
        token_info = self.auth.get_access_token()
        if not token_info:
            raise Exception("No se pudo obtener un token válido. Verifica el KOMMO_AUTH_CODE en GitHub Secrets.")
        return {"Authorization": f"Bearer {token_info['access_token']}"}

    def _format_date(self, timestamp):
        """Convierte Unix timestamp a ISO 8601 para Supabase."""
        if not timestamp: return None
        try:
            return datetime.fromtimestamp(int(timestamp)).isoformat()
        except:
            return None

    def get_users(self):
        """Obtiene la lista de usuarios/agentes de la cuenta."""
        url = f"{self.base_url}/users"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json().get("_embedded", {}).get("users", [])
        return []

    def get_leads_custom_fields(self):
        """Obtiene el catálogo de campos personalizados para mapeo por ID."""
        url = f"{self.base_url}/leads/custom_fields"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json().get("_embedded", {}).get("custom_fields", [])
        return []

    def get_lead_chats(self, lead_id):
        """Extrae el historial de chats de un lead buscando en eventos y conversaciones."""
        # Endpoint de eventos filtrado por lead
        url_events = f"{self.auth.base_url}/api/v4/events"
        params_events = {
            "filter[entity_id]": lead_id,
            "filter[entity]": "lead",
            "limit": 100
        }
        
        chat_content = ""
        try:
            resp_events = requests.get(url_events, headers=self._get_headers(), params=params_events)
            if resp_events.status_code == 200:
                events = resp_events.json().get("_embedded", {}).get("events", [])
                for event in events:
                    # Buscamos eventos de chat (entrantes y salientes)
                    if "chat_message" in event["type"]:
                        # Intentar extraer texto si está presente (para widgets de terceros)
                        value = event.get("value_after", [{}])[0]
                        if "text" in value:
                            text = value["text"]
                            prefix = "CLIENTE: " if "incoming" in event["type"] else "AGENTE: "
                            chat_content += f"[{event['created_at']}] {prefix}{text}\n"
                        elif "message" in value and "talk_id" in value["message"]:
                            # Para WABA (WhatsApp Oficial), solo sabemos que hubo un mensaje
                            # El texto real usualmente se captura via Webhook en tiempo real
                            chat_content += f"[{event['created_at']}] [Mensajeria WABA Detectada - Ref: {value['message']['talk_id']}]\n"
            
            # 2. Fallback a Notas (algunas integraciones guardan el texto aquí)
            url_notes = f"{self.auth.base_url}/api/v4/leads/{lead_id}/notes"
            resp_notes = requests.get(url_notes, headers=self._get_headers())
            if resp_notes.status_code == 200:
                notes = resp_notes.json().get("_embedded", {}).get("notes", [])
                for note in notes:
                    if note["note_type"] in ["common", "service_message"]:
                        text = note.get("params", {}).get("text", "")
                        if text:
                            chat_content += f"[{note['created_at']}] NOTA: {text}\n"
        except Exception as e:
            logging.error(f"Error al obtener chats o notas para el lead {lead_id}: {e}")
        
        # Retornar el contenido del chat acumulado
        return chat_content

    def get_lead_chats_json(self, lead_id):
        """Extrae el historial de chats de un lead como lista JSON para análisis estructurado."""
        url_events = f"{self.auth.base_url}/api/v4/events"
        params_events = {
            "filter[entity_id]": lead_id,
            "filter[entity]": "lead",
            "limit": 100
        }
        
        chat_list = []
        try:
            # Dar un pequeño respiro a la API de Kommo para que indexe el mensaje recién enviado
            time.sleep(2)
            
            # Intento 1
            headers = self._get_headers()
            resp_events = requests.get(url_events, headers=headers, params=params_events)
            
            # Si da 401, forzar renovación y reintentar
            if resp_events.status_code == 401:
                logging.warning(f"401 Detectado para lead {lead_id}. Forzando renovación de token...")
                token_info = self.auth.get_access_token(force_refresh=True)
                if not token_info:
                    logging.error(f"Fallo crítico: No se pudo obtener un nuevo token para lead {lead_id}")
                    return []
                headers = {"Authorization": f"Bearer {token_info['access_token']}"}
                resp_events = requests.get(url_events, headers=headers, params=params_events)
            
            logging.info(f"API EVENTS lead {lead_id} -> Status: {resp_events.status_code}")
            
            if resp_events.status_code == 200:
                events_data = resp_events.json()
                events = events_data.get("_embedded", {}).get("events", [])
                logging.info(f"API EVENTS lead {lead_id} -> Encontrados {len(events)} eventos")
                
                # Ordenar cronológicamente ascendente
                events = sorted(events, key=lambda x: x.get("created_at", 0))
                
                for event in events:
                    event_type = event.get("type", "")
                    logging.info(f"Procesando evento tipo: {event_type}")

                    # Buscamos 'chat_message' o 'message' en el tipo de evento
                    if "message" in event_type or "chat" in event_type:
                        value = event.get("value_after", [{}])[0]
                        
                        # Ruta 1: Directo en value
                        text = value.get("text", "")
                        # Ruta 2: Dentro de message
                        if not text and "message" in value:
                            text = value["message"].get("text", "")
                        # Ruta 3: Dentro de note (a veces los chats se guardan como notas)
                        if not text and "note" in value:
                            text = value["note"].get("text", "")

                        if not text:
                            # Si sigue sin haber texto, logeamos la estructura para debug
                            logging.debug(f"Evento sin texto detectado. Estructura: {value}")
                            continue
                            
                        is_incoming = "incoming" in event_type
                        direction = "entrante" if is_incoming else "saliente"
                        
                        author_name = "Cliente" if is_incoming else "Agente"
                        
                        time_obj = datetime.fromtimestamp(event["created_at"], tz=timezone.utc)
                            
                        chat_list.append({
                            "time": time_obj.isoformat(),
                            "from": direction,
                            "text": text,
                            "author": author_name
                        })
                
                logging.info(f"API EVENTS lead {lead_id} -> Mensajes procesados: {len(chat_list)}")
            else:
                logging.error(f"Error API Kommo Events: {resp_events.text}")
        except Exception as e:
            logging.error(f"Error al obtener chats JSON para lead {lead_id}: {e}")
            
        return chat_list

    def get_global_stats(self):
        """Obtiene estadísticas agregadas de los leads."""
        url = f"{self.base_url}/leads/stats"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return response.json()
        return {}

    def normalize_channel(self, source):
        """Lógica de normalización ampliada para MMM."""
        if not source: return "Organic/Direct"
        s = source.lower()
        if any(x in s for x in ['fb', 'facebook', 'ig', 'instagram', 'meta', 'fbc', 'fbp']):
            return "Meta_Ads"
        if any(x in s for x in ['google', 'cpc', 'g-search', 'adwords', 'gclid', 'goog']):
            return "Google_Ads"
        if 'wa' in s or 'whatsapp' in s:
            return "WhatsApp_Direct"
        return "Other_Paid"

    def flatten_lead(self, lead):
        """Aplanado avanzado del lead con normalización MMM."""
        flat_data = {
            "id": lead.get("id"),
            "name": lead.get("name"),
            "price": lead.get("price"),
            "responsible_user_id": lead.get("responsible_user_id"),
            "status_id": lead.get("status_id"),
            "pipeline_id": lead.get("pipeline_id"),
            "created_at": self._format_date(lead.get("created_at")),
            "updated_at": self._format_date(lead.get("updated_at")),
            "utm_source": None,
            "utm_medium": None,
            "utm_campaign": None,
            "utm_content": None,
            "utm_term": None,
            "gclid": None,
            "fbc": None,
            "fbp": None
        }

        # Extraer Custom Fields
        custom_fields = lead.get("custom_fields_values", [])
        if custom_fields:
            for field in custom_fields:
                name = field.get("field_name", "").lower()
                val = field.get("values", [{}])[0].get("value")
                if not val: continue
                
                if "utm_source" in name: flat_data["utm_source"] = val
                elif "utm_medium" in name: flat_data["utm_medium"] = val
                elif "utm_campaign" in name: flat_data["utm_campaign"] = val
                elif "utm_content" in name: flat_data["utm_content"] = val
                elif "utm_term" in name: flat_data["utm_term"] = val
                elif "gclid" in name: flat_data["gclid"] = val
                elif "fbc" in name: flat_data["fbc"] = val
                elif "fbp" in name: flat_data["fbp"] = val

        # Normalizar Canal: Usar utm_source o el gclid/fbc si están presentes
        source_val = flat_data.get("utm_source") or ""
        if flat_data.get("gclid"): source_val += " google_gclid"
        if flat_data.get("fbc") or flat_data.get("fbp"): source_val += " meta_pixel"
        
        flat_data["marketing_channel"] = self.normalize_channel(source_val)
        
        # Extraer Etiquetas (Tags)
        tags_list = [tag.get("name") for tag in lead.get("_embedded", {}).get("tags", [])]
        flat_data["tags"] = tags_list
        
        return flat_data

    def fetch_unsorted_leads(self, max_pages=5):
        """Extrae leads que aún están en la sección 'Entrantes' (Unsorted)."""
        all_unsorted = []
        url = f"https://{self.subdomain}.kommo.com/api/v4/leads/unsorted"
        
        for page in range(1, max_pages + 1):
            params = {"page": page, "limit": 50}
            logging.info(f"Extrayendo leads entrantes (Unsorted) - Página {page}...")
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("_embedded", {}).get("unsorted", [])
                if not items: break
                
                for item in items:
                    # Extraer el objeto lead embebido en el unsorted
                    embedded_leads = item.get("_embedded", {}).get("leads", [])
                    if embedded_leads:
                        lead = embedded_leads[0]
                        flat = self.flatten_lead(lead)
                        # Marcar como 'Unsorted' (Status 0 temporalmente)
                        flat["status_id"] = 0 
                        all_unsorted.append(flat)
                
                if len(items) < 50: break
                time.sleep(self.rate_limit_delay)
            else:
                break
                
        return pd.DataFrame(all_unsorted)

    def fetch_all_leads(self, days_back=2, max_pages=50):
        """Extracción masiva filtrada por fecha de creación."""
        all_leads = []
        url = f"{self.base_url}/leads"
        
        # Filtro de fecha en Unix Timestamp
        since_timestamp = int(time.time()) - (days_back * 86400)
        
        params = {
            "with": "contacts", 
            "limit": 250,
            "filter[created_at][from]": since_timestamp
        }
        
        for page in range(1, max_pages + 1):
            params["page"] = page
            logging.info(f"Extrayendo leads recientes (Página {page})...")
            response = requests.get(url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                data = response.json()
                if not data: break
                leads = data.get("_embedded", {}).get("leads", [])
                all_leads.extend([self.flatten_lead(l) for l in leads])
                if len(leads) < 250: break
                time.sleep(self.rate_limit_delay)
            else:
                break
                
        return pd.DataFrame(all_leads)
