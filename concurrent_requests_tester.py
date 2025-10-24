import time
import requests
import threading
from collections import defaultdict


# Usage: python concurrent_requests_tester.py <server_url>

def spam_requests(url, duration=10, num_threads=20):
    """Spam requests with multiple threads as fast as possible"""
    print(f"[SPAMMER] Starting spam attack with {num_threads} threads for {duration} seconds...")
    results = {'success': 0, 'rate_limited': 0, 'errors': 0}
    results_lock = threading.Lock()
    stop_flag = threading.Event()

    def spam_worker():
        while not stop_flag.is_set():
            try:
                response = requests.get(url, timeout=2)
                with results_lock:
                    if response.status_code == 200:
                        results['success'] += 1
                    elif response.status_code == 429:
                        results['rate_limited'] += 1
                    total = results['success'] + results['rate_limited']
                    print(
                        f"[SPAMMER] Total: {total} | Success: {results['success']} | Blocked: {results['rate_limited']}",
                        end='\r')
            except Exception as e:
                with results_lock:
                    results['errors'] += 1

    # Start spam threads
    threads = []
    start = time.time()

    for i in range(num_threads):
        t = threading.Thread(target=spam_worker, daemon=True)
        t.start()
        threads.append(t)

    # Run for duration
    time.sleep(duration)
    stop_flag.set()

    # Wait for threads to finish
    for t in threads:
        t.join(timeout=1)

    elapsed = time.time() - start
    print(f"\n[SPAMMER] Results after {elapsed:.1f}s:")
    print(f"  Success: {results['success']} ({results['success'] / elapsed:.2f} req/s)")
    print(f"  Rate Limited (429): {results['rate_limited']}")
    print(f"  Errors: {results['errors']}")
    print(f"  Total throughput: {(results['success'] + results['rate_limited']) / elapsed:.2f} req/s")
    return results


def controlled_requests(url, rate=4, duration=10):
    """Send requests at controlled rate (just below limit)"""
    print(f"[CONTROLLED] Sending {rate} req/s for {duration} seconds...")
    results = {'success': 0, 'rate_limited': 0, 'errors': 0}
    interval = 1.0 / rate

    start = time.time()
    count = 0

    while time.time() - start < duration:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                results['success'] += 1
            elif response.status_code == 429:
                results['rate_limited'] += 1
            count += 1
            print(f"[CONTROLLED] Request {count}: {response.status_code}")
        except Exception as e:
            results['errors'] += 1

        time.sleep(interval)

    elapsed = time.time() - start
    print(f"\n[CONTROLLED] Results after {elapsed:.1f}s:")
    print(f"  Success: {results['success']} ({results['success'] / elapsed:.2f} req/s)")
    print(f"  Rate Limited (429): {results['rate_limited']}")
    print(f"  Errors: {results['errors']}")
    return results


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python concurrent_requests_tester.py <server_url>")
        print("Example: python concurrent_requests_tester.py http://localhost:8000/books/book1.pdf")
        sys.exit(1)

    url = sys.argv[1]
    duration = 10

    print("=" * 60)
    print("Rate Limit Testing")
    print("=" * 60)
    print(f"Target: {url}")
    print(f"Duration: {duration}s")
    print(f"Rate Limit: 5 req/s")
    print("=" * 60)

    # Test 1: Spam attack
    print("\n### TEST 1: Spam Attack (20 concurrent threads)")
    spam_results = spam_requests(url, duration, num_threads=20)

    time.sleep(2)  # Cool down

    # Test 2: Controlled rate
    print("\n### TEST 2: Controlled Rate (4 req/s)")
    controlled_results = controlled_requests(url, rate=4, duration=duration)

    # Summary
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"Spam Attack (20 threads):")
    print(f"  - Successful: {spam_results['success']}")
    print(f"  - Blocked (429): {spam_results['rate_limited']}")
    if spam_results['success'] + spam_results['rate_limited'] > 0:
        print(
            f"  - Success Rate: {spam_results['success'] / (spam_results['success'] + spam_results['rate_limited']) * 100:.1f}%")
    print(f"\nControlled (4 req/s):")
    print(f"  - Successful: {controlled_results['success']}")
    print(f"  - Blocked (429): {controlled_results['rate_limited']}")
    if controlled_results['success'] + controlled_results['rate_limited'] > 0:
        print(
            f"  - Success Rate: {controlled_results['success'] / (controlled_results['success'] + controlled_results['rate_limited']) * 100:.1f}%")


if __name__ == "__main__":
    main()