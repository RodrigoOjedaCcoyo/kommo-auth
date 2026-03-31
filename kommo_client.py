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

    def get_lead_main_contact_id(self, lead_id):
        """Obtiene el ID del contacto principal de un lead."""
        url = f"{self.auth.base_url}/api/v4/leads/{lead_id}?with=contacts"
        try:
            resp = requests.get(url, headers=self._get_headers())
            if resp.status_code == 200:
                contacts = resp.json().get("_embedded", {}).get("contacts", [])
                for c in contacts:
                    if c.get("is_main"):
                        return c.get("id")
                return contacts[0].get("id") if contacts else None
        except Exception as e:
            logging.error(f"Error obteniendo contacto del lead {lead_id}: {e}")
        return None

    def get_talk_messages(self, talk_id=None, chat_uuid=None):
        """Obtiene el historial de mensajes de un Talk o Chat UUID."""
        headers = self._get_headers()
        
        # Opción A: Talk ID (Clásico)
        if talk_id:
            url = f"{self.base_url}/chats/talks/{talk_id}/messages"
            try:
                resp = requests.get(url, headers=headers)
                if resp.status_code == 200:
                    return self._process_api_messages(resp.json())
                else:
                    logging.warning(f"Talk ID {talk_id} falló con status {resp.status_code}")
            except Exception as e:
                logging.error(f"Error en Talk ID {talk_id}: {e}")

        # Opción B: Chat UUID (El ID largo que vimos en logs)
        if chat_uuid:
            # Endpoint alternativo para WABA: /messages?filter[chat_id][]={uuid}
            url = f"{self.base_url}/messages"
            params = {"filter[chat_id][]": chat_uuid}
            try:
                resp = requests.get(url, headers=headers, params=params)
                logging.info(f"DEBUG_UUID Scan para {chat_uuid}: Status {resp.status_code}")
                if resp.status_code == 200:
                    return self._process_api_messages(resp.json())
            except Exception as e:
                logging.error(f"Error en Chat UUID {chat_uuid}: {e}")
        
        return []

    def _process_events(self, data):
        """Extrae DIÁLOGOS (Vendedor + Cliente) de los eventos de Kommo."""
        evs = data.get("_embedded", {}).get("events", [])
        extracted = []
        
        if evs:
            # 🔍 LOG DE DIAGNÓSTICO TOTAL: Ver tipos de TODOS los eventos
            types_found = [e.get("type") for e in evs]
            logging.info(f"DEBUG_EVENT_TYPES: {types_found}")
            
            # Ver estructura cruda de los primeros 3 para no saturar
            for i, sample in enumerate(evs[:3]):
                logging.info(f"DEBUG_RAW_EVENT_{i}: {json.dumps(sample)}")

        for e in evs:
            text = None
            etype = e.get("type", "")
            # Ajustamos autor basándonos en el tipo de evento
            author_type = "Vendedor" if "outgoing" in etype or "agent" in etype else "Cliente"
            
            # 💡 KOMMO WABA HACK: El texto suele estar en value_after -> message -> text
            val = e.get("value_after")
            if isinstance(val, list) and len(val) > 0:
                text = val[0].get("message", {}).get("text") or val[0].get("text")
            elif isinstance(val, dict):
                # Caso B: Estructura de objeto directo
                text = val.get("message", {}).get("text") or val.get("text") or val.get("message_text")

            if text:
                ts = e.get("created_at")
                dt = datetime.fromtimestamp(ts)
                extracted.append({
                    "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "author": author_type,
                    "text": text
                })
        return extracted

    def _process_api_messages(self, data):
        """Procesa el JSON de mensajes del API a nuestro formato unificado."""
        msgs = data.get("_embedded", {}).get("messages", [])
        extracted = []
        for m in msgs:
            text = m.get("text")
            if text:
                timestamp = m.get("created_at")
                dt = datetime.fromtimestamp(timestamp)
                author = m.get("author", {}).get("name", "Sistema")
                extracted.append({
                    "date": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "author": author,
                    "text": text
                })
        return extracted

    def get_lead_chats_json(self, lead_id, talk_id_direct=None, chat_uuid=None):
        """Extrae historial completo universal (Último Intento API)."""
        combined_messages = []
        
        # 1. Probar con los IDs directos del Webhook
        combined_messages.extend(self.get_talk_messages(talk_id=talk_id_direct, chat_uuid=chat_uuid))
        
        headers = self._get_headers()
        
        # 2. ESCÁNER: Probar /events filtrado por lead
        url_events = f"{self.base_url}/events"
        params_events = {"filter[entity_id]": lead_id, "filter[entity]": "lead", "limit": 50}
        try:
            resp = requests.get(url_events, headers=headers, params=params_events)
            logging.info(f"DEBUG_SCAN 2 (Events): Status {resp.status_code}")
            if resp.status_code == 200:
                evs = resp.json().get("_embedded", {}).get("events", [])
                for e in evs:
                    if "message" in e["type"] or "chat" in e["type"]:
                         logging.info(f"DEBUG_SCAN 2 Evento detectado type={e['type']} data={str(e.get('value_after'))[:200]}")
        except: pass

        # 3. ESCÁNER: Probar notas del contacto (Muchas WABA viven aquí)
        contact_id = self.get_lead_main_contact_id(lead_id)
        if contact_id:
            url_notes = f"{self.base_url}/contacts/{contact_id}/notes"
            try:
                resp = requests.get(url_notes, headers=headers)
                logging.info(f"DEBUG_SCAN 3 (Contact Notes): Status {resp.status_code}")
                if resp.status_code == 200:
                    notes = resp.json().get("_embedded", {}).get("notes", [])
                    for n in notes:
                        if "message" in n["note_type"]:
                            logging.info(f"DEBUG_SCAN 3 Nota detectada type={n['note_type']} params={str(n.get('params'))[:200]}")
            except: pass

        # 3. Fallback a EVENTOS y NOTAS (para otras integraciones no-WABA)
        entities = [("lead", lead_id)]
        if contact_id: entities.append(("contact", contact_id))

        for entity_type, entity_id in entities:
            # Eventos
            url_events = f"{self.auth.base_url}/api/v4/events"
            params_events = {"filter[entity_id]": entity_id, "filter[entity]": entity_type, "limit": 100}
            try:
                resp_events = requests.get(url_events, headers=headers, params=params_events)
                if resp_events.status_code == 200:
                    events = resp_events.json().get("_embedded", {}).get("events", [])
                    for e in events:
                        if "message" in e["type"] or "chat" in e["type"]:
                            val_after = e.get("value_after")
                            val = val_after[0] if isinstance(val_after, list) and val_after else (val_after if isinstance(val_after, dict) else {})
                            text = val.get("text") or val.get("message", {}).get("text")
                            if text:
                                combined_messages.append({
                                    "time": e["created_at"],
                                    "from": "entrante" if "incoming" in e["type"] else "saliente",
                                    "text": text,
                                    "author": "Cliente" if "incoming" in e["type"] else "Agente",
                                    "id": e["id"]
                                })
            except: pass

            # Notas
            url_notes = f"{self.auth.base_url}/api/v4/{entity_type}s/{entity_id}/notes"
            try:
                resp_notes = requests.get(url_notes, headers=headers)
                if resp_notes.status_code == 200:
                    notes = resp_notes.json().get("_embedded", {}).get("notes", [])
                    for n in notes:
                        if n["note_type"] in ["common", "service_message", "incoming_chat_message", "outgoing_chat_message"]:
                            text = n.get("params", {}).get("text")
                            if text:
                                combined_messages.append({
                                    "time": n["created_at"],
                                    "from": "saliente" if n["note_type"] in ["common", "service_message"] else "entrante",
                                    "text": text,
                                    "author": "Agente" if n["note_type"] in ["common", "service_message"] else "Cliente",
                                    "id": n["id"]
                                })
            except: pass

        # 4. Limpieza final y orden cronológico
        seen_ids = set()
        seen_texts = set()
        unique_messages = []
        combined_messages = sorted(combined_messages, key=lambda x: str(x["time"]))
        
        for m in combined_messages:
            msg_id = m.get("id")
            txt = m.get("text", "").strip()
            # Evitar duplicados por ID o por texto idéntico en tiempo similar
            if msg_id not in seen_ids and txt not in seen_texts:
                seen_ids.add(msg_id)
                seen_texts.add(txt)
                unique_messages.append({
                    "time": datetime.fromtimestamp(int(m["time"]), tz=timezone.utc).isoformat() if isinstance(m["time"], (int,float)) else m["time"],
                    "from": m["from"],
                    "text": m["text"],
                    "author": m["author"]
                })

        logging.info(f"CAPTURA UNIVERSAL lead {lead_id} -> {len(unique_messages)} mensajes consolidados.")
        return unique_messages

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
