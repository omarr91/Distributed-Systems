# client/load_generator.py

import threading
import time
from queue import Queue
from Models import Request


def simulate_user(scheduler, user_id, result_list=None):
    request = Request(id=user_id, query=f"Query {user_id}")
    response = scheduler.handle_request(request)
    if(result_list != None):
        result_list.put(response)
        return
    return response

def run_load_test(scheduler, num_users=1000):
    threads = []
    collected = Queue()

    start_time = time.time()

    for i in range(num_users):
        t = threading.Thread(target=simulate_user, args=(scheduler, i,collected))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    end_time = time.time()
    results = []
    while not collected.empty():
        results.append(collected.get())

    throughput = len(results) / (end_time - start_time)

    workers_ids = set()
    for i in range(len(results)):
        workers_ids.add(results[i]["worker_id"])
    
    num_of_workers = len(workers_ids)
    avg_latency = 0
    for i in range(len(results)): avg_latency += results[i]["latency"]

    avg_latency = avg_latency / len(results)

    print(f"Average Latency: {avg_latency:.3f}\t\tThroughput: {throughput:.3f}\t\tNumber of Workers: {num_of_workers}")