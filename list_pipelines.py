from kommo_client import KommoClient
import json

def list_all_pipelines():
    client = KommoClient()
    url = f"{client.base_url}/leads/pipelines"
    
    try:
        response = client.requests.get(url, headers=client._get_headers())
        if response.status_code == 200:
            pipelines = response.json().get("_embedded", {}).get("pipelines", [])
            print("\n=== LISTADO DE EMBUDOS (PIPELINES) EN KOMMO ===")
            for pipe in pipelines:
                print(f"ID: {pipe['id']} | NOMBRE: {pipe['name']}")
            print("==============================================\n")
        else:
            print(f"Error al obtener pipelines: {response.text}")
    except Exception as e:
        # Si no tiene requests en el objeto client directamente, usamos requests normal
        import requests
        resp = requests.get(url, headers=client._get_headers())
        if resp.status_code == 200:
            pipelines = resp.json().get("_embedded", {}).get("pipelines", [])
            print("\n=== LISTADO DE EMBUDOS (PIPELINES) EN KOMMO ===")
            for pipe in pipelines:
                print(f"ID: {pipe['id']} | NOMBRE: {pipe['name']}")
            print("==============================================\n")
        else:
            print(f"Error: {resp.text}")

if __name__ == "__main__":
    list_all_pipelines()
