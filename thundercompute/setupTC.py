import os
import subprocess
from ThunderComputeAPI import create_instance,list_instances,delete_instance,add_instance_port

create_instance()
try:
    response = list_instances()

    add_instance_port(0,8000)
    instances = response.json()
    print(type(instances["0"]["uuid"]))
    print("a7a")
    os.environ["WORKER_URLS"] = "https://"+instances["0"]["uuid"]+"-8000.thundercompute.net"
    print("a7a2")
    cmd1 = "tnr scp ..\\worker 0:/tmp/worker"
    cmd2 = "tnr connect 0"
    cmd3 = "cd /tmp/worker && bash setup.sh"
    subprocess.run([cmd1.split()],capture_output=True)
    print("a7a3")
    subprocess.run([cmd2.split()],capture_output=True)
    print("a7a4")
except :
    delete_instance(0)
    print("[!] Error detected and instance deleted")
    