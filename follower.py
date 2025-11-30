"""
Follower node for key-value store.
The follower accepts replication requests from the leader.
"""
import os
import logging
import threading
from typing import Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="KV Store Follower")

# Pydantic models
class ReplicateRequest(BaseModel):
    key: str
    value: str

class ReplicateResponse(BaseModel):
    status: str
    key: str
    value: str

class ReadResponse(BaseModel):
    key: str
    value: str

class DataResponse(BaseModel):
    data: Dict[str, str]

class HealthResponse(BaseModel):
    status: str
    role: str
    name: str

# In-memory key-value store
data_store = {}
data_lock = threading.RLock()

# Configuration
NODE_NAME = os.environ.get('NODE_NAME', 'follower')

logger.info(f"Follower '{NODE_NAME}' started")


@app.post('/replicate', response_model=ReplicateResponse)
async def replicate(request: ReplicateRequest):
    """
    Replication endpoint: accepts key-value updates from the leader.
    """
    try:
        key = request.key
        value = request.value

        # Apply the replication
        with data_lock:
            data_store[key] = value

        logger.info(f"Replicated: key={key}, value={value}")

        return ReplicateResponse(status="success", key=key, value=value)

    except Exception as e:
        logger.error(f"Error in replicate: {e}")
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
        role="follower",
        name=NODE_NAME
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    uvicorn.run(app, host='0.0.0.0', port=port)

