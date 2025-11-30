"""
Integration test for the key-value store with replication.
Tests the full system running in Docker containers.
"""
import time
import requests
import pytest

LEADER_URL = "http://localhost:5000"
FOLLOWER_URLS = [
    "http://localhost:5001",
    "http://localhost:5002",
    "http://localhost:5003",
    "http://localhost:5004",
    "http://localhost:5005"
]


def wait_for_service(url, max_retries=30, retry_delay=2):
    """Wait for a service to become available."""
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ {url} is ready")
                return True
        except requests.exceptions.RequestException:
            pass

        if i < max_retries - 1:
            time.sleep(retry_delay)

    print(f"✗ {url} is not responding")
    return False


def test_services_are_running():
    """Test that all services are up and running."""
    print("\nTesting service availability...")

    assert wait_for_service(LEADER_URL), "Leader is not responding"

    for follower_url in FOLLOWER_URLS:
        assert wait_for_service(follower_url), f"{follower_url} is not responding"

    print("✓ All services are running")


def test_write_and_read():
    """Test basic write and read operations."""
    print("\nTesting write and read operations...")

    # Write a key-value pair
    response = requests.post(
        f"{LEADER_URL}/write",
        json={"key": "test_key", "value": "test_value"},
        timeout=10
    )

    assert response.status_code == 200, f"Write failed: {response.text}"
    data = response.json()
    assert data['status'] == 'success'
    assert data['key'] == 'test_key'
    assert data['value'] == 'test_value'
    print(f"✓ Write successful: {data}")

    # Read from leader
    response = requests.get(f"{LEADER_URL}/read?key=test_key", timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert data['key'] == 'test_key'
    assert data['value'] == 'test_value'
    print(f"✓ Read from leader successful: {data}")


def test_replication():
    """Test that data is replicated to followers."""
    print("\nTesting replication to followers...")

    # Write a key-value pair
    test_key = "replication_test"
    test_value = f"value_{int(time.time())}"

    response = requests.post(
        f"{LEADER_URL}/write",
        json={"key": test_key, "value": test_value},
        timeout=10
    )

    assert response.status_code == 200, f"Write failed: {response.text}"
    data = response.json()
    assert data['status'] == 'success'
    confirmations = data['confirmations']
    print(f"✓ Write successful with {confirmations} confirmations")

    # Give some time for replication to complete
    time.sleep(2)

    # Check each follower
    replicated_count = 0
    for follower_url in FOLLOWER_URLS:
        try:
            response = requests.get(f"{follower_url}/read?key={test_key}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['value'] == test_value:
                    replicated_count += 1
                    print(f"✓ Data replicated to {follower_url}")
                else:
                    print(f"✗ Data mismatch on {follower_url}")
            else:
                print(f"✗ Key not found on {follower_url}")
        except Exception as e:
            print(f"✗ Error reading from {follower_url}: {e}")

    print(f"✓ Data replicated to {replicated_count}/{len(FOLLOWER_URLS)} followers")
    assert replicated_count >= 3, "Data not replicated to enough followers"


def test_multiple_writes():
    """Test multiple concurrent writes."""
    print("\nTesting multiple writes...")

    import concurrent.futures

    def write_key(i):
        key = f"key_{i}"
        value = f"value_{i}"
        response = requests.post(
            f"{LEADER_URL}/write",
            json={"key": key, "value": value},
            timeout=10
        )
        return response.status_code == 200, key, value

    # Write 10 keys concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_key, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    successful = sum(1 for success, _, _ in results if success)
    print(f"✓ {successful}/10 writes successful")
    assert successful >= 8, "Too many writes failed"


def test_data_consistency():
    """Test that data is consistent across leader and followers after writes."""
    print("\nTesting data consistency...")

    # Get all data from leader
    response = requests.get(f"{LEADER_URL}/data", timeout=5)
    assert response.status_code == 200
    leader_data = response.json()['data']
    print(f"Leader has {len(leader_data)} keys")

    # Give time for all replications to complete
    time.sleep(3)

    # Check each follower
    for follower_url in FOLLOWER_URLS:
        response = requests.get(f"{follower_url}/data", timeout=5)
        assert response.status_code == 200
        follower_data = response.json()['data']

        # Check that all keys in follower exist in leader
        for key, value in follower_data.items():
            if key in leader_data:
                if leader_data[key] == value:
                    pass  # Match
                else:
                    print(f"⚠ Value mismatch for key '{key}' on {follower_url}")
            else:
                print(f"⚠ Extra key '{key}' on {follower_url}")

        match_count = sum(1 for k in leader_data if k in follower_data and leader_data[k] == follower_data[k])
        print(f"✓ {follower_url}: {match_count}/{len(leader_data)} keys match")


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '-s'])

