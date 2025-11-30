"""
Leader node for key-value store with semi-synchronous replication.
The leader accepts write requests and replicates them to followers.
"""
import os
import time
import random
import logging
import threading
from typing import Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="KV Store Leader")

# Pydantic models for request/response validation
class WriteRequest(BaseModel):
    key: str
    value: str

class WriteResponse(BaseModel):
    status: str
    key: str
    value: str
    confirmations: int
    latency_ms: float

class ReadResponse(BaseModel):
    key: str
    value: str

class DataResponse(BaseModel):
    data: Dict[str, str]

class HealthResponse(BaseModel):
    status: str
    role: str
    write_quorum: int
    followers: int

# In-memory key-value store
data_store = {}
data_lock = threading.RLock()

# Configuration from environment variables
WRITE_QUORUM = int(os.environ.get('WRITE_QUORUM', 3))
MIN_DELAY = int(os.environ.get('MIN_DELAY', 0))  # milliseconds
MAX_DELAY = int(os.environ.get('MAX_DELAY', 1000))  # milliseconds
FOLLOWERS = os.environ.get('FOLLOWERS', '').split(',')
FOLLOWERS = [f.strip() for f in FOLLOWERS if f.strip()]

logger.info(f"Leader started with WRITE_QUORUM={WRITE_QUORUM}")
logger.info(f"Replication delay range: [{MIN_DELAY}ms, {MAX_DELAY}ms]")
logger.info(f"Followers: {FOLLOWERS}")


def replicate_to_follower(follower_url, key, value):
    """
    Replicate a key-value pair to a single follower with simulated network delay.
    The delay represents the total time including network latency and processing.
    Returns (success, delay_ms) tuple.
    """
    # Generate a random delay to simulate network lag
    delay_seconds = random.uniform(MIN_DELAY / 1000.0, MAX_DELAY / 1000.0)

    try:
        start_time = time.time()

        # Send the replication request (should be very fast in local network)
        response = requests.post(
            f"{follower_url}/replicate",
            json={"key": key, "value": value},
            timeout=5
        )

        # Calculate actual request time
        actual_time = time.time() - start_time

        # Sleep for the remaining delay to simulate network lag
        # The simulated delay should be the total time, so we subtract actual request time
        remaining_delay = max(0, delay_seconds - actual_time)
        if remaining_delay > 0:
            time.sleep(remaining_delay)

        success = response.status_code == 200
        delay_ms = delay_seconds * 1000

        if success:
            logger.info(f"Replicated {key} to {follower_url} (simulated delay: {delay_ms:.0f}ms, actual: {actual_time*1000:.0f}ms)")
        else:
            logger.warning(f"Failed to replicate {key} to {follower_url}: {response.status_code}")
        return success, delay_ms
    except Exception as e:
        logger.error(f"Error replicating to {follower_url}: {e}")
        return False, delay_seconds * 1000


def replicate_to_followers(key, value):
    """
    Replicate a key-value pair to all followers concurrently.
    Uses semi-synchronous replication: waits for WRITE_QUORUM confirmations.
    Returns as soon as quorum is reached (or quorum cannot be achieved).
    Returns (success, num_confirmations).
    """
    if not FOLLOWERS:
        logger.warning("No followers configured")
        return True, 0

    confirmations = 0
    failures = 0

    # Create executor without context manager to avoid waiting for all tasks
    executor = ThreadPoolExecutor(max_workers=len(FOLLOWERS))

    try:
        # Start all replication requests concurrently
        # This ensures all delays start at approximately the same time
        futures = {
            executor.submit(replicate_to_follower, follower, key, value): follower
            for follower in FOLLOWERS
        }

        # Wait only until quorum is reached (semi-synchronous)
        for future in as_completed(futures):
            follower = futures[future]
            try:
                success, delay_ms = future.result()
                if success:
                    confirmations += 1
                    # Return immediately once quorum is reached
                    if confirmations >= WRITE_QUORUM:
                        logger.info(f"Write quorum reached: {confirmations}/{WRITE_QUORUM}")
                        # Don't wait for remaining tasks - shutdown without waiting
                        executor.shutdown(wait=False)
                        return True, confirmations
                else:
                    failures += 1
            except Exception as e:
                logger.error(f"Exception from replication to {follower}: {e}")
                failures += 1

            # Early failure detection: if we can't possibly reach quorum
            remaining = len(FOLLOWERS) - (confirmations + failures)
            if confirmations + remaining < WRITE_QUORUM:
                logger.warning(f"Cannot reach quorum: {confirmations} confirmations, {failures} failures, {remaining} remaining")
                executor.shutdown(wait=False)
                return False, confirmations

        # All followers completed but quorum not reached
        success = confirmations >= WRITE_QUORUM
        logger.info(f"Replication completed: {confirmations}/{len(FOLLOWERS)} confirmations (quorum: {WRITE_QUORUM})")
        return success, confirmations
    finally:
        # Always shutdown the executor, but don't wait if not already shut down
        if not executor._shutdown:
            executor.shutdown(wait=False)


@app.post('/write', response_model=WriteResponse)
async def write(request: WriteRequest):
    """
    Write endpoint: accepts a key-value pair and replicates to followers.
    Returns success only if write quorum is achieved.
    """
    try:
        key = request.key
        value = request.value

        start_time = time.time()

        # Write to leader's store first
        with data_lock:
            data_store[key] = value

        logger.info(f"Write request: key={key}, value={value}")

        # Replicate to followers (semi-synchronous)
        success, confirmations = replicate_to_followers(key, value)

        latency = (time.time() - start_time) * 1000  # milliseconds

        if success:
            return WriteResponse(
                status="success",
                key=key,
                value=value,
                confirmations=confirmations,
                latency_ms=latency
            )
        else:
            # Rollback is not implemented in this simple version
            # In production, you might want to implement two-phase commit
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "failed",
                    "error": f"Write quorum not achieved: {confirmations}/{WRITE_QUORUM}",
                    "confirmations": confirmations,
                    "latency_ms": latency
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in write: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/read', response_model=ReadResponse)
async def read(key: str = Query(..., description="The key to read")):
    """
    Read endpoint: returns the value for a given key.
    """
    try:
        with data_lock:
            if key in data_store:
                return ReadResponse(key=key, value=data_store[key])
            else:
                raise HTTPException(status_code=404, detail="Key not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/data', response_model=DataResponse)
async def get_all_data():
    """
    Returns all data in the store (for testing/debugging).
    """
    try:
        with data_lock:
            return DataResponse(data=data_store.copy())
    except Exception as e:
        logger.error(f"Error in get_all_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/health', response_model=HealthResponse)
async def health():
    """
    Health check endpoint.
    """
    return HealthResponse(
        status="healthy",
        role="leader",
        write_quorum=WRITE_QUORUM,
        followers=len(FOLLOWERS)
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    uvicorn.run(app, host='0.0.0.0', port=port)

