import os
import subprocess
from ThunderComputeAPI import create_instance,list_instances,delete_instance,add_instance_port
import argparse
import time



script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, r"..\master", "workers_urls.txt")
TNR = r"C:\Program Files (x86)\tnr"
parser = argparse.ArgumentParser()
parser.add_argument("-n",default=1,type=int,help="Number of instances to create")
parser.add_argument("-D",action="store_true")
args = parser.parse_args()


if(args.D):
    if(os.path.exists(output_path)):
        os.remove(output_path)
    response = list_instances()
    instances = response.json()
    instances_ids = [k for k, v in instances.items()]
    if len(instances_ids) == 0:
        print("[!] No instances are found")
        exit()
    for i in instances_ids:
        delete_instance(i)
    print("[!] Deleted all instances")
    exit()

try:
    for n in range(args.n):
        create_instance()
    response = list_instances()
    instances = response.json()
    instances_ids = [k for k, v in instances.items()]
    print(instances_ids)
    workers_urls = ""
    for i in instances_ids:
        add_instance_port(i,8000)
        if i == instances_ids[0]:
            workers_urls = "https://"+instances[str(i)]["uuid"]+"-8000.thundercompute.net"
            continue
        workers_urls += ",https://"+instances[str(i)]["uuid"]+"-8000.thundercompute.net"

    
    with open(output_path,"w") as f:
        f.write(workers_urls)
        f.close()
    time.sleep(60)
    for i in instances_ids:
        while True:
            output = subprocess.run(["cmd","/c","tnr","scp",r"C:\Users\LOQ\Desktop\ASU\Distributed\project\dist project\worker",f"{i}:/tmp/worker"],capture_output=True,text=True)
            if output.returncode != 0:
                print(f"Copy failed for instance {i}: {output.stderr}")
                if "status: STARTING" in output.stderr or "status: QUEUED" in output.stderr:
                    time.sleep(10)
                    continue
                else:
                    break
            else:
                print(f"Copy success for instance {i}")
                break

except :
    response = list_instances()
    instances = response.json()
    instances_ids = [k for k, v in instances.items()]
    for i in instances_ids:
        delete_instance(i)
    print("[!] Deleted all instances")
    