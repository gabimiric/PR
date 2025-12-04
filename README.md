# Network Programming

### Lab 4 - Leaders and Followers
### Miricinschi Gabriel

## Overview

This project implements a distributed key-value store with **single-leader replication**. The system consists of one leader node that accepts write requests and replicates data to multiple follower nodes using **semi-synchronous replication**. 

**Key Features:**
- Single leader accepts all writes
- 5 follower nodes for data replication
- Semi-synchronous replication with configurable write quorum
- Simulated network delays (0-1000ms) to test replication behavior
- Concurrent request handling on both leader and followers
- RESTful API with JSON communication
- Docker containerized deployment

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Python 3.11+** (for running tests locally)

## Installation

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Running the System

### Start All Services with Docker Compose

```bash
docker-compose up -d --build
```

This command will:
- Build Docker images for the leader and followers
- Start 1 leader container (port 5000)
- Start 5 follower containers (ports 5001-5005)
- Configure the network between containers

### Stop All Services

```bash
docker-compose down
```

### View Logs

View leader logs:
```bash
docker logs kv-leader
```

View specific follower logs:
```bash
docker logs kv-follower1
```

View all logs:
```bash
docker-compose logs -f
```

## Configuration

The system is configured via environment variables in `docker-compose.yml`:

- **WRITE_QUORUM**: Number of follower confirmations required (default: 3)
- **MIN_DELAY**: Minimum simulated network delay in milliseconds (default: 0)
- **MAX_DELAY**: Maximum simulated network delay in milliseconds (default: 1000)
- **FOLLOWERS**: Comma-separated list of follower URLs

## API Endpoints

### Leader (http://localhost:5000)

**Write a key-value pair:**
```bash
curl -X POST http://localhost:5000/write \
  -H "Content-Type: application/json" \
  -d '{"key": "mykey", "value": "myvalue"}'
```

**Read a value:**
```bash
curl http://localhost:5000/read?key=mykey
```

**Get all data:**
```bash
curl http://localhost:5000/data
```

**Health check:**
```bash
curl http://localhost:5000/health
```

### Followers (http://localhost:5001-5005)

**Read a value:**
```bash
curl http://localhost:5001/read?key=mykey
```

**Get all data:**
```bash
curl http://localhost:5001/data
```

## Running Tests

### Integration Tests

Verify the system works correctly:
```bash
python test_integration.py
```

This runs 5 tests:
1. Service availability check
2. Write and read operations
3. Replication to followers
4. Multiple concurrent writes
5. Data consistency across all nodes

### Performance Analysis

Analyze system performance with different write quorum values:
```bash
python performance_analysis.py
```

This script:
- Tests write quorum values from 1 to 5
- Performs ~100 concurrent writes (10 at a time)
- Measures average latency for each quorum value
- Checks data consistency after all writes
- Generates a plot showing Quorum vs. Latency

**Expected Results:**
- **Quorum 1**: ~180ms average latency (waits for fastest follower)
- **Quorum 2**: ~250ms average latency (waits for 2nd fastest)
- **Quorum 3**: ~450ms average latency (waits for 3rd fastest)
- **Quorum 4**: ~500ms average latency (waits for 4th fastest)
- **Quorum 5**: ~700ms average latency (waits for all followers)
