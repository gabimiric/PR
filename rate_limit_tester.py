import time
import concurrent.futures
import requests
import sys

# Spam test: send many requests as fast as possible with multiple threads
def spam_test(url, num_requests=50, max_workers=10):
    print(f"\n[TEST 1: SPAM] Sending {num_requests} requests with {max_workers} concurrent threads...")

    results = {'success': 0, 'blocked': 0, 'errors': 0}

    def make_request(_):
        # Each thread sends a single request and categorizes the result
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return 'success'
            elif r.status_code == 429:
                return 'blocked'
            else:
                return 'errors'
        except:
            return 'errors'

    start = time.time()
    # Use ThreadPoolExecutor for concurrency
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for r in executor.map(make_request, range(num_requests)):
            results[r] += 1
    elapsed = time.time() - start

    # Print summarized results
    print(f"\nResults:")
    print(f"  Time taken: {elapsed:.2f}s")
    print(f"  Successful (200): {results['success']}")
    print(f"  Blocked (429): {results['blocked']}")
    print(f"  Errors: {results['errors']}")
    if results['success'] + results['blocked'] > 0:
        print(f"  Throughput (successful req/s): {results['success'] / elapsed:.2f}")

    return results

# Controlled test: send requests at a fixed rate below the server limit
def controlled_test(url, num_requests=20, rate=4):
    print(f"\n[TEST 2: CONTROLLED] Sending {num_requests} requests at {rate} req/s...")
    interval = 1.0 / rate
    results = {'success': 0, 'blocked': 0, 'errors': 0}
    start = time.time()

    for i in range(num_requests):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                results['success'] += 1
                print(f"  Request {i+1}: 200 OK")
            elif r.status_code == 429:
                results['blocked'] += 1
                print(f"  Request {i+1}: 429 BLOCKED")
            else:
                results['errors'] += 1
                print(f"  Request {i+1}: {r.status_code} ERROR")
        except:
            results['errors'] += 1
            print(f"  Request {i+1}: CONNECTION ERROR")
        time.sleep(interval)

    elapsed = time.time() - start
    print(f"\nResults:")
    print(f"  Time taken: {elapsed:.2f}s")
    print(f"  Successful (200): {results['success']}")
    print(f"  Blocked (429): {results['blocked']}")
    print(f"  Errors: {results['errors']}")
    if results['success'] + results['blocked'] > 0:
        print(f"  Throughput (successful req/s): {results['success'] / elapsed:.2f}")
    return results

def main():
    if len(sys.argv) < 2:
        print("Usage: python rate_limit_tester.py <server_url>")
        sys.exit(1)

    url = sys.argv[1]
    print("="*60)
    print("Rate Limit Testing (5 req/s limit)")
    print("="*60)
    print(f"Target: {url}\n")

    # Test 1: spam many requests to see rate limiter in action
    spam_results = spam_test(url, num_requests=50, max_workers=10)
    print("\n" + "-"*60)
    time.sleep(2)  # cool down between tests

    # Test 2: controlled rate below limit to see all requests succeed
    controlled_results = controlled_test(url, num_requests=20, rate=4)

    # Summary of both tests
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("\nSpam Attack (50 requests, 10 concurrent threads):")
    print(f"  ✓ {spam_results['success']} successful")
    print(f"  ✗ {spam_results['blocked']} blocked (429)")
    print(f"  ✗ {spam_results['errors']} errors")
    if spam_results['success'] + spam_results['blocked'] > 0:
        blocked_percent = spam_results['blocked'] / (spam_results['success'] + spam_results['blocked']) * 100
        print(f"  → Rate limiter blocked {blocked_percent:.1f}% of requests")

    print("\nControlled Rate (20 requests at 4 req/s):")
    print(f"  ✓ {controlled_results['success']} successful")
    print(f"  ✗ {controlled_results['blocked']} blocked (429)")
    print(f"  ✗ {controlled_results['errors']} errors")
    print(f"  → All requests successful: {'YES ✓' if controlled_results['blocked']==0 else 'NO ✗'}")
    print("="*60)

if __name__ == "__main__":
    main()
