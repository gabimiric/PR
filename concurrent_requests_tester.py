import time
import concurrent.futures
import requests
import sys


def make_request(url, session):
    start = time.time()
    try:
        response = session.get(url)
        return time.time() - start, response.status_code
    except Exception as e:
        return time.time() - start, str(e)


def main():
    if len(sys.argv) < 2:
        print("Usage: python concurrent_test.py <server_url>")
        sys.exit(1)

    base_url = sys.argv[1]
    num_requests = 10

    # Create a session for connection reuse
    session = requests.Session()

    # Test with multiple concurrent requests
    print(f"Making {num_requests} concurrent requests to {base_url}")
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request, base_url, session) for _ in range(num_requests)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    total_time = time.time() - start_time

    # Analyze results
    request_times = [r[0] for r in results]
    statuses = [r[1] for r in results]

    print(f"\nResults:")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average request time: {sum(request_times) / len(request_times):.2f}s")
    print(f"Min request time: {min(request_times):.2f}s")
    print(f"Max request time: {max(request_times):.2f}s")
    print(f"Status codes: {statuses}")


if __name__ == "__main__":
    main()