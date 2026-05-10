# client/load_generator.py

import threading
import time
from queue import Queue
from Models import Request
import requests
import random


TEST_QUERIES = [
    "What is the capital of France?",
    "Explain quantum computing in simple terms.",
    "Write a short poem about the ocean.",
    "What are the main causes of climate change?",
    "How does a neural network learn?",
    "What is the difference between Python and JavaScript?",
    "Summarize the history of the Roman Empire.",
    "What is machine learning?",
    "How do black holes form?",
    "Write a haiku about autumn.",
    "What are the benefits of exercise?",
    "Explain the theory of relativity.",
    "What is the meaning of life?",
    "How does the internet work?",
    "What is the difference between AI and machine learning?",
    "Write a short story about a robot.",
    "What are the planets in our solar system?",
    "How do vaccines work?",
    "What is blockchain technology?",
    "Explain recursion in programming.",
    "What is the fastest animal on Earth?",
    "How does photosynthesis work?",
    "What is the difference between RAM and ROM?",
    "Write a joke about programmers.",
    "What caused World War I?",
]

def simulate_user(scheduler, user_id, result_list=None):
    query = random.choice(TEST_QUERIES)
    response = requests.post("http://127.0.0.1/query",json={"query":query})
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