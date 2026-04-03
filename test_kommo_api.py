import json
import logging
import requests
from kommo_client import KommoClient

logging.basicConfig(level=logging.WARNING)

def run_test():
    try:
        kommo = KommoClient()
        headers = kommo._get_headers()
        talk_id = 1108

        print("========================================")
        print("  PRUEBA 1: API /messages (MÉTODO NUEVO)")
        print("========================================")
        url1 = f"{kommo.base_url}/messages"
        params1 = {"filter[talk_id][]": talk_id}
        resp1 = requests.get(url1, headers=headers, params=params1)
        print(f"Status /messages: {resp1.status_code}")
        if resp1.status_code == 200:
            print(json.dumps(resp1.json(), indent=2)[:1000] + "\n... (truncado si es muy largo)")
        else:
            print(resp1.text)

        print("\n========================================")
        print("  PRUEBA 2: API /chats (MÉTODO CLÁSICO)")
        print("========================================")
        url2 = f"{kommo.base_url}/chats/talks/{talk_id}/messages"
        resp2 = requests.get(url2, headers=headers)
        print(f"Status /chats/talks: {resp2.status_code}")
        if resp2.status_code == 200:
            print(json.dumps(resp2.json(), indent=2)[:1000] + "\n... (truncado si es muy largo)")
        else:
            print(resp2.text)

    except Exception as e:
        print(f"Error fatal en script local: {e}")

if __name__ == "__main__":
    run_test()
