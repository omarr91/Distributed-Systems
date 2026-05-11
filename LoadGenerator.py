# client/load_generator.py

import threading
import time
from queue import Queue
import requests
import random
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-u",default=1,help="Number of concurrent users.")
args = parser.parse_args()



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

def simulate_user(user_id, result_list=None):
    query = random.choice(TEST_QUERIES)
    response = requests.post("http://127.0.0.1/query",json={"query":query})
    if(result_list != None):
        result_list.put(response)
        return
    return response

def run_load_test(num_users):
    threads = []
    collected = Queue()

    start_time = time.time()

    for i in range(num_users):
        t = threading.Thread(target=simulate_user, args=(i,collected))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    end_time = time.time()
    results = []
    while not collected.empty():
        results.append(collected.get())

    total_time = 0
    for z in results:
        total_time += results[z]["worker_response"]["processing_time"]

    throughput = len(results) / (total_time)
    avg_latency = total_time / len(results)

    print(f"Number of users: {num_users}\t\tAverage Latency: {avg_latency:.3f}\t\tThroughput: {throughput:.3f}\t\t")


run_load_test(args.u)