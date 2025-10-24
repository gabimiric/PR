# Network Programming

### Lab 1 - Multithreading & Concurrency
### Miricinschi Gabriel

## Overview
This lab extends the HTTP server from Lab 0 with:
- **Multithreading**: Handle multiple requests concurrently
- **Request Counter**: Track requests per file with thread-safe implementation
- **Rate Limiting**: Limit requests per client IP (5 req/s)

## Changes from Lab 0

### 1. Multithreading Implementation

#### Modified `server.py` main loop:
```python
            # Create a new thread to handle the client request
            client_thread = threading.Thread(
                target=handle_request,
                args=(client_socket, base_dir),
                daemon=True  # This allows the thread to be terminated when main program exits
            )
            client_thread.start()
```

#### Added 1-second delay to simulate work:
```python
    elif os.path.isfile(abs_path):
        # Serve the file with the correct MIME type
        if SIMULATE_WORK:
            time.sleep(1)  # Simulate 1 second of work
```

### 2. Request Counter with Thread Safety

#### Thread-safe counter implementation:
```python
request_counts = defaultdict(int)
counter_lock = threading.Lock()

# When serving a file:
with counter_lock:
    rel_file_path = os.path.relpath(abs_path, base_dir)
    request_counts[rel_file_path] = request_counts.get(rel_file_path, 0) + 1
```

#### Display in directory listing:
```python
count = current_counts.get(rel_file_path, 0)
html.append(f'<li><a href="{link}">{display_name}</a> — {count} requests</li>')
```

### 3. Rate Limiting Implementation

```python
RATE_LIMIT = 5  # max requests per second
rate_limit_window = 1  # seconds
client_requests = defaultdict(lambda: deque())
rate_lock = threading.Lock()

# In handle_request():
    with rate_lock:
        reqs = client_requests[client_ip]
        # Remove timestamps older than 1 second
        while reqs and now - reqs[0] > rate_limit_window:
            reqs.popleft()

        if len(reqs) >= RATE_LIMIT:
            # Too many requests
            response_body = b'429 Too Many Requests'
            response = build_header(429, 'text/plain', len(response_body)) + response_body
            client_socket.sendall(response)
            client_socket.close()
            return

        # Record this request timestamp
        reqs.append(now)
```

## Testing Scripts

### 1. concurrent_requests_tester.py  
1. Sends multiple requests simultaneously to test server performance and concurrency.
2. Measures total time, request times, throughput, and enforces rate limits.

**Usage:**
```bash
python concurrent_requests_tester.py http://localhost:8000/books/HellScream.pdf
```

### 2. rate_limit_tester.py
1. Limits each client IP to a set number of requests per second (e.g., 5 req/s).
2. Ensures that clients exceeding the limit receive HTTP 429 responses, protecting the server from overload.

```bash
python rate_limit_tester.py http://localhost:8000/books/HellScream.pdf 
```

## Test Results

### Part 1: Performance Test for both servers with concurrency

#### Single-thread server.py (lab 0)

<img width="975" height="111" alt="image" src="https://github.com/user-attachments/assets/252d690c-68cc-400e-a7de-a62eab5182a6" />

#### Multithread server.py (lab 1)

<img width="964" height="114" alt="image" src="https://github.com/user-attachments/assets/3b13a740-0fa6-4347-bed6-e111bb9e8dfb" />

**Analysis:**
- **Single-Thread**: ALl requests succesful done in ~10 seconds (sequential with 1 req/s)
- **Multithread**: All requests done in ~1.05 seconds (half of them falling due to rate limiting)
  
---

### Part 2: Counter Race Condition Test
Tested by running concurrent_requests_tester.py 3 times (5 valid requests x 3 = 15)
#### Test with naive counter (no lock):

<img width="364" height="563" alt="image" src="https://github.com/user-attachments/assets/d9f3a1c4-0a74-4017-9bbf-c552c9cf7f2a" />

#### Test with naive counter off:

<img width="371" height="534" alt="image" src="https://github.com/user-attachments/assets/2ed5c54c-c184-4dee-b08d-fa169ad6ad9b" />

**Analysis:** 
- **Without lock**: Race condition causes lost updates (4/15 counted)
- **With lock**: All 15 requests counted correctly

---

### Part 3: Rate Limiting Test

<img width="888" height="834" alt="image" src="https://github.com/user-attachments/assets/7208351c-3ed7-405a-8dbc-d8364bd23626" />
<img width="487" height="270" alt="image" src="https://github.com/user-attachments/assets/75c4411d-0870-4a07-9bed-40dc48ec0540" />





**Screenshot:** [Insert screenshot of rate limit test output]

**Analysis:**
- **Spammer** (unlimited rate): Successfully sent only ~5 req/s, with 45 requests blocked (429 status)
- **Controlled** (4 req/s): All requests succesful
