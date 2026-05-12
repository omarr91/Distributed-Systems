# client/load_generator.py

import threading
import time
from queue import Queue
import requests
import random
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

parser = argparse.ArgumentParser()
parser.add_argument("-u",default=1,help="Number of concurrent users.",type=int)
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

def make_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    return session

def simulate_user(user_id, result_queue):
    query = random.choice(TEST_QUERIES)
    try:
        response = requests.post(
            "http://127.0.0.1/query",
            json={"query": query},
            timeout=300
        )
        result_queue.put(response)
    except Exception as e:
        print(f"User {user_id} failed: {type(e).__name__}: {e}")
        result_queue.put(None)

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

    failed_requests = 0
    total_time = 0
    for z in results:
        if z.status_code != 200:
            failed_requests += 1
            continue
        z = z.json()
        total_time += int(z["worker_response"]["processing_time"])
    if total_time == 0:
        total_time = end_time-start_time
    throughput = len(results) / (total_time)
    avg_latency = total_time / len(results)

    print(f"Number of users: {num_users}\t\tAverage Latency: {avg_latency:.3f}\t\tThroughput: {throughput:.3f}\t\tFailed requests: {failed_requests}")


run_load_test(args.u)