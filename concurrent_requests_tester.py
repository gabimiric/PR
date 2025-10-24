import time
import concurrent.futures
import requests
import sys

def make_request(url):
    start = time.time()
    try:
        r = requests.get(url)
        return time.time() - start, r.status_code
    except Exception as e:
        return time.time() - start, str(e)

def main():
    if len(sys.argv) != 2:
        print("Usage: python concurrent_requests_tester.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    num_requests = 10

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        results = list(executor.map(make_request, [url]*num_requests))
    total = time.time() - start

    times = [r[0] for r in results]
    statuses = [r[1] for r in results]

    print(f"Total time: {total:.2f}s")
    print(f"Average: {sum(times)/len(times):.2f}s")
    print(f"Min: {min(times):.2f}s")
    print(f"Max: {max(times):.2f}s")
    print(f"Statuses: {statuses}")

if __name__ == "__main__":
    main()
