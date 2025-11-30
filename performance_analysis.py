"""
Performance Analysis for Key-Value Store with Semi-Synchronous Replication

This script analyzes the system performance by:
1. Testing different write quorum values (1-5)
2. Making ~100 concurrent writes (10 at a time) on 10 keys
3. Plotting write quorum vs. average latency
4. Checking data consistency between leader and followers
5. Explaining the results
"""
import time
import requests
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import logging
import sys
import subprocess
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
LEADER_URL = "http://localhost:5000"
FOLLOWER_URLS = [
    "http://localhost:5001",
    "http://localhost:5002",
    "http://localhost:5003",
    "http://localhost:5004",
    "http://localhost:5005"
]

NUM_KEYS = 10
NUM_WRITES_PER_KEY = 10  # 10 writes per key = 100 total writes
CONCURRENT_WRITES = 10  # 10 at a time
WRITE_QUORUM_VALUES = [1, 2, 3, 4, 5]


def wait_for_service(url: str, max_retries: int = 30, retry_delay: int = 2) -> bool:
    """Wait for a service to become available."""
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                logger.info(f"✓ {url} is ready")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            time.sleep(retry_delay)

    logger.error(f"✗ {url} is not responding")
    return False


def wait_for_all_services() -> bool:
    """Wait for all services to be available."""
    logger.info("Waiting for all services to start...")

    if not wait_for_service(LEADER_URL):
        return False

    for follower_url in FOLLOWER_URLS:
        if not wait_for_service(follower_url):
            return False

    logger.info("✓ All services are ready")
    return True


def perform_write(key: str, value: str) -> Tuple[bool, float, int]:
    """
    Perform a single write operation.
    Returns (success, latency_ms, confirmations)
    """
    try:
        response = requests.post(
            f"{LEADER_URL}/write",
            json={"key": key, "value": value},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            return True, data['latency_ms'], data['confirmations']
        else:
            # Write failed due to quorum not reached
            try:
                error_detail = response.json().get('detail', {})
                latency = error_detail.get('latency_ms', 0)
                confirmations = error_detail.get('confirmations', 0)
                return False, latency, confirmations
            except:
                return False, 0, 0
    except Exception as e:
        logger.error(f"Error performing write: {e}")
        return False, 0, 0


def perform_concurrent_writes(num_keys: int, writes_per_key: int, max_workers: int) -> List[Dict]:
    """
    Perform concurrent writes on multiple keys.
    Returns a list of write results.
    """
    results = []
    write_tasks = []

    # Generate all write tasks
    for key_idx in range(num_keys):
        key = f"key_{key_idx}"
        for write_idx in range(writes_per_key):
            value = f"value_{key_idx}_{write_idx}_{int(time.time() * 1000)}"
            write_tasks.append((key, value))

    logger.info(f"Starting {len(write_tasks)} writes with {max_workers} concurrent workers...")

    start_time = time.time()

    # Execute writes concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(perform_write, key, value): (key, value)
            for key, value in write_tasks
        }

        completed = 0
        for future in as_completed(futures):
            key, value = futures[future]
            try:
                success, latency, confirmations = future.result()
                results.append({
                    'key': key,
                    'value': value,
                    'success': success,
                    'latency_ms': latency,
                    'confirmations': confirmations
                })
                completed += 1
                if completed % 10 == 0:
                    logger.info(f"Completed {completed}/{len(write_tasks)} writes")
            except Exception as e:
                logger.error(f"Write task failed: {e}")

    total_time = time.time() - start_time
    logger.info(f"All writes completed in {total_time:.2f} seconds")

    return results


def get_node_data(url: str) -> Dict[str, str]:
    """Get all data from a node."""
    try:
        response = requests.get(f"{url}/data", timeout=5)
        if response.status_code == 200:
            return response.json()['data']
        else:
            logger.error(f"Failed to get data from {url}: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error getting data from {url}: {e}")
        return {}


def check_data_consistency() -> Dict:
    """
    Check if data in followers matches data in leader.
    Returns consistency report.
    """
    logger.info("Checking data consistency...")

    # Wait a bit for replication to complete
    time.sleep(3)

    leader_data = get_node_data(LEADER_URL)
    logger.info(f"Leader has {len(leader_data)} keys")

    consistency_report = {
        'leader_keys': len(leader_data),
        'follower_reports': []
    }

    for follower_url in FOLLOWER_URLS:
        follower_data = get_node_data(follower_url)

        # Compare with leader
        matching_keys = 0
        mismatched_keys = 0
        missing_keys = 0

        for key, value in leader_data.items():
            if key in follower_data:
                if follower_data[key] == value:
                    matching_keys += 1
                else:
                    mismatched_keys += 1
            else:
                missing_keys += 1

        consistency_percentage = (matching_keys / len(leader_data) * 100) if len(leader_data) > 0 else 0

        report = {
            'url': follower_url,
            'total_keys': len(follower_data),
            'matching_keys': matching_keys,
            'mismatched_keys': mismatched_keys,
            'missing_keys': missing_keys,
            'consistency_percentage': consistency_percentage
        }

        consistency_report['follower_reports'].append(report)

        logger.info(f"{follower_url}: {consistency_percentage:.1f}% consistent "
                   f"({matching_keys} match, {missing_keys} missing, {mismatched_keys} mismatch)")

    return consistency_report


def restart_docker_compose_with_quorum(quorum: int) -> bool:
    """
    Restart docker-compose with a specific write quorum value.
    """
    logger.info(f"Restarting system with WRITE_QUORUM={quorum}...")

    # Stop existing containers
    subprocess.run(["docker-compose", "down"],
                  capture_output=True,
                  text=True,
                  shell=True)

    time.sleep(2)

    # Start with new configuration
    env = os.environ.copy()

    # Modify docker-compose.yml temporarily or use environment override
    # For simplicity, we'll modify the environment variable in the subprocess
    # Note: This requires docker-compose to support environment variable override

    # Read docker-compose.yml and modify WRITE_QUORUM
    with open('docker-compose.yml', 'r') as f:
        compose_content = f.read()

    # Replace WRITE_QUORUM value
    import re
    modified_content = re.sub(
        r'- WRITE_QUORUM=\d+',
        f'- WRITE_QUORUM={quorum}',
        compose_content
    )

    # Write temporary file
    with open('docker-compose.tmp.yml', 'w') as f:
        f.write(modified_content)

    # Start with modified file
    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.tmp.yml", "up", "-d"],
        capture_output=True,
        text=True,
        shell=True
    )

    if result.returncode != 0:
        logger.error(f"Failed to start docker-compose: {result.stderr}")
        return False

    # Wait for services to be ready
    time.sleep(5)

    if not wait_for_all_services():
        logger.error("Services did not start properly")
        return False

    logger.info(f"✓ System restarted with WRITE_QUORUM={quorum}")
    return True


def run_performance_test_for_quorum(quorum: int) -> Dict:
    """
    Run performance test for a specific write quorum value.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"TESTING WITH WRITE_QUORUM = {quorum}")
    logger.info(f"{'='*60}\n")

    # Perform concurrent writes
    results = perform_concurrent_writes(
        num_keys=NUM_KEYS,
        writes_per_key=NUM_WRITES_PER_KEY,
        max_workers=CONCURRENT_WRITES
    )

    # Calculate statistics
    successful_writes = [r for r in results if r['success']]
    failed_writes = [r for r in results if not r['success']]

    if successful_writes:
        latencies = [r['latency_ms'] for r in successful_writes]
        avg_latency = np.mean(latencies)
        median_latency = np.median(latencies)
        p95_latency = np.percentile(latencies, 95)
        p99_latency = np.percentile(latencies, 99)
        min_latency = np.min(latencies)
        max_latency = np.max(latencies)
    else:
        avg_latency = median_latency = p95_latency = p99_latency = min_latency = max_latency = 0

    success_rate = len(successful_writes) / len(results) * 100 if results else 0

    # Check consistency
    consistency_report = check_data_consistency()

    stats = {
        'quorum': quorum,
        'total_writes': len(results),
        'successful_writes': len(successful_writes),
        'failed_writes': len(failed_writes),
        'success_rate': success_rate,
        'avg_latency': avg_latency,
        'median_latency': median_latency,
        'p95_latency': p95_latency,
        'p99_latency': p99_latency,
        'min_latency': min_latency,
        'max_latency': max_latency,
        'consistency_report': consistency_report
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"RESULTS FOR WRITE_QUORUM = {quorum}")
    logger.info(f"{'='*60}")
    logger.info(f"Total writes: {stats['total_writes']}")
    logger.info(f"Successful: {stats['successful_writes']} ({stats['success_rate']:.1f}%)")
    logger.info(f"Failed: {stats['failed_writes']}")
    logger.info(f"Average latency: {stats['avg_latency']:.2f} ms")
    logger.info(f"Median latency: {stats['median_latency']:.2f} ms")
    logger.info(f"P95 latency: {stats['p95_latency']:.2f} ms")
    logger.info(f"P99 latency: {stats['p99_latency']:.2f} ms")
    logger.info(f"Min/Max latency: {stats['min_latency']:.2f} / {stats['max_latency']:.2f} ms")
    logger.info(f"{'='*60}\n")

    return stats


def plot_results(all_stats: List[Dict]):
    """
    Create visualization plot for the performance analysis.
    Single graph showing latency metrics vs write quorum.
    """
    logger.info("Creating performance plot...")

    quorums = [s['quorum'] for s in all_stats]
    # Convert from milliseconds to seconds
    avg_latencies = [s['avg_latency'] / 1000.0 for s in all_stats]
    median_latencies = [s['median_latency'] / 1000.0 for s in all_stats]
    p95_latencies = [s['p95_latency'] / 1000.0 for s in all_stats]
    p99_latencies = [s['p99_latency'] / 1000.0 for s in all_stats]

    # Create single figure
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot all latency metrics
    ax.plot(quorums, avg_latencies, 'b-o', linewidth=2, markersize=8, label='mean')
    ax.plot(quorums, median_latencies, 'orange', linewidth=2, markersize=8, label='median')
    ax.plot(quorums, p95_latencies, 'g-^', linewidth=2, markersize=8, label='p95')
    ax.plot(quorums, p99_latencies, 'r-s', linewidth=2, markersize=8, label='p99')

    # Labels and title
    ax.set_xlabel('Quorum value', fontsize=12)
    ax.set_ylabel('Latency (s)', fontsize=12)
    ax.set_title('Quorum vs. Latency, random delay in range [0, 1000ms]', fontsize=12)

    # Legend
    ax.legend(fontsize=10, loc='upper left')

    # Set x-axis ticks to show only integer quorum values
    ax.set_xticks(quorums)

    plt.tight_layout()

    # Show plot only (don't save)
    plt.show()

def main():
    """Main function to run the complete performance analysis."""
    logger.info("Starting Performance Analysis")
    logger.info(f"Configuration:")
    logger.info(f"  - Number of keys: {NUM_KEYS}")
    logger.info(f"  - Writes per key: {NUM_WRITES_PER_KEY}")
    logger.info(f"  - Total writes: {NUM_KEYS * NUM_WRITES_PER_KEY}")
    logger.info(f"  - Concurrent writes: {CONCURRENT_WRITES}")
    logger.info(f"  - Write quorum values to test: {WRITE_QUORUM_VALUES}")

    all_stats = []

    for quorum in WRITE_QUORUM_VALUES:
        # Restart system with new quorum
        if not restart_docker_compose_with_quorum(quorum):
            logger.error(f"Failed to restart system with quorum {quorum}")
            continue

        # Run performance test
        stats = run_performance_test_for_quorum(quorum)
        all_stats.append(stats)

        # Small delay between tests
        time.sleep(2)

    if not all_stats:
        logger.error("No test results available")
        return

    # Create plots
    plot_results(all_stats)

    logger.info("✓ Performance analysis completed successfully")

    # Cleanup: restore original docker-compose
    if os.path.exists('docker-compose.tmp.yml'):
        os.remove('docker-compose.tmp.yml')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in performance analysis: {e}", exc_info=True)
        sys.exit(1)

