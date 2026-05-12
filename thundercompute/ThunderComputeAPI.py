import requests
import dotenv
import os

dotenv.load_dotenv()
api_key = os.getenv("API_KEY")

def list_instances():
    response = requests.get("https://api.thundercompute.com:8443/v1/instances/list",headers={"Authorization":"Bearer "+api_key,"Content-type":"application/json"})
    return response

def create_instance():
    response = requests.post("https://api.thundercompute.com:8443/v1/instances/create",headers={"Authorization":"Bearer "+api_key,"Content-type":"application/json"},
                             json={"cpu_cores":8,
                                   "disk_size_gb":100,
                                   "gpu_type":"L40",
                                   "mode":"prototyping",
                                   "num_gpus":2,
                                   "template":"ollama"
                                   })
    return response

def delete_instance(id):
    response = requests.post(f"https://api.thundercompute.com:8443/v1/instances/{id}/delete",headers={"Authorization":"Bearer "+api_key,"Content-type":"application/json"})
    if response.status_code == 200:
        return True
    return False

def add_instance_port(id,portnum):
    response = requests.post(f"https://api.thundercompute.com:8443/v1/instances/{id}/modify",headers={"Authorization":"Bearer "+api_key,"Content-type":"application/json"},json={"add_ports":[portnum]})
    if response.status_code == 200:
        return True
    return False

print(create_instance().text)