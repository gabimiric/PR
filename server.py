import os
import sys
import socket
import mimetypes
import urllib.parse
import threading
import time
import concurrent

from collections import defaultdict
from collections import deque

request_counts = defaultdict(int)
counter_lock = threading.Lock()

RATE_LIMIT = 5  # max requests per second
rate_limit_window = 1  # seconds
client_requests = defaultdict(lambda: deque())
rate_lock = threading.Lock()

# Configuration
NAIVE_MODE = False  # Set to True to demonstrate race condition
SIMULATE_WORK = False  # Set to True to add 1-second delay for testing

# Usage: python server.py <directory> <port>

# Build HTTP response headers
def build_header(status_code, content_type=None, content_length=0):
    status_messages = {
        200: "OK",
        404: "Not Found",
        429: "Too Many Requests"
    }
    reason = status_messages.get(status_code, "Unknown")
    header = f"HTTP/1.1 {status_code} {reason}\r\n"
    header += "Connection: close\r\n"
    if content_type:
        header += f"Content-Type: {content_type}\r\n"
    if content_length:
        header += f"Content-Length: {content_length}\r\n"
    header += "\r\n"
    return header.encode()

# Recursively generate HTML for all files/folders under a directory
def generate_directory_listing(directory, rel_path=""):
    items = sorted(os.listdir(directory))
    html = []

    # Get a thread-safe snapshot of the current request counts
    with counter_lock:
        current_counts = request_counts.copy()

    for item in items:
        if item == "index.html":
            continue  # Skip index.html from the listing

        full_path = os.path.join(directory, item)
        display_name = item + ('/' if os.path.isdir(full_path) else '')
        link = '/' + urllib.parse.quote(os.path.join(rel_path, item).replace('\\', '/'))

        if os.path.isdir(full_path):
            # Use <details> for collapsible folders
            html.append(f'<li><details><summary>{display_name}</summary>')
            html.append('<ul>')
            html.append(generate_directory_listing(full_path, os.path.join(rel_path, item)))
            html.append('</ul></details></li>')

        else:
            # Only include files of these types
            if item.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.gif')):
                # Get count from our thread-safe snapshot
                rel_file_path = os.path.join(rel_path, item)
                count = current_counts.get(rel_file_path, 0)
                html.append(f'<li><a href="{link}">{display_name}</a> — {count} requests</li>')

    return '\n'.join(html)  # Return as a single string
# Serve the main index.html page and inject dynamic file list
def serve_index_page(client_socket, base_dir):
    index_file = os.path.join(base_dir, "index.html")
    if not os.path.isfile(index_file):
        # If no index.html, return 404
        client_socket.sendall(build_header(404, 'text/plain', len(b'404 Not Found')) + b'404 Not Found')
        client_socket.close()
        return

    with open(index_file, 'r', encoding='utf-8') as f:
        html = f.read()

    # Generate the dynamic list for all folders/files
    file_list = generate_directory_listing(base_dir)

    # Inject into placeholder in index.html
    html = html.replace('<ul id="file-list"></ul>', f'<ul id="file-list">\n{file_list}</ul>')

    # Send HTTP response
    body = html.encode('utf-8')
    header = build_header(200, 'text/html; charset=utf-8', len(body))
    client_socket.sendall(header + body)
    client_socket.close()

# Handle an individual client HTTP request
def handle_request(client_socket, base_dir):
    request = b""
    while b"\r\n\r\n" not in request:
        chunk = client_socket.recv(1024)
        if not chunk:
            break
        request += chunk

    try:
        request_line = request.decode().split("\r\n")[0]
        method, path, _ = request_line.split()
    except ValueError:
        client_socket.close()
        return

    # Rate limiting
    client_ip = client_socket.getpeername()[0]
    now = time.time()

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

    # Debug prints
    print("Base directory:", os.path.abspath(base_dir))
    print("Raw request:", request.decode())
    print("Requested path:", path)

    if method != "GET":
        # Only support GET requests
        response = build_header(404, 'text/plain', len(b'Unsupported method')) + b'Unsupported method'
        client_socket.sendall(response)
        client_socket.close()
        return

    # Handle favicon.ico automatically
    if path == "/favicon.ico":
        response = build_header(200, 'image/x-icon', 0)  # empty response
        client_socket.sendall(response)
        client_socket.close()
        return

    # Serve the main index page if root is requested
    if path == "/" or path == "":
        serve_index_page(client_socket, base_dir)
        return

    # Normalize path to avoid path traversal
    rel_path = urllib.parse.unquote(path.lstrip('/'))
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))

    # Ensure path is within base_dir
    if not abs_path.startswith(os.path.abspath(base_dir)):
        # Requested path is outside base_dir → return 404
        response_body = b'404 Not Found'
        response = build_header(404, 'text/plain', len(response_body)) + response_body
        client_socket.sendall(response)
        client_socket.close()
        return

    # Normalize requested path to prevent path traversal
    if os.path.isdir(abs_path):
        # Return a recursive directory listing for folders
        body = generate_directory_listing(abs_path, rel_path).encode('utf-8')
        header = build_header(200, 'text/html; charset=utf-8', len(body))
        client_socket.sendall(header + body)

    elif os.path.isfile(abs_path):
        # Serve the file with the correct MIME type
        if SIMULATE_WORK:
            time.sleep(1)  # Simulate 1 second of work

        # Update request count for this file
        if NAIVE_MODE:
            # RACE CONDITION
            rel_file_path = os.path.relpath(abs_path, base_dir)
            current_count = request_counts.get(rel_file_path, 0)
            time.sleep(0.001)
            request_counts[rel_file_path] = current_count + 1
            print(
                f"[Thread {threading.current_thread().name}] Updated {rel_file_path} to {request_counts[rel_file_path]}")
        else:
            # THREAD-SAFE
            with counter_lock:
                rel_file_path = os.path.relpath(abs_path, base_dir)
                request_counts[rel_file_path] = request_counts.get(rel_file_path, 0) + 1

        mime_type, _ = mimetypes.guess_type(abs_path)
        if not (mime_type and (
                mime_type.startswith('text/html') or mime_type == 'image/png' or mime_type == 'application/pdf')):
            response_body = b'404 Not Found'
            response = build_header(404, 'text/plain', len(response_body)) + response_body
            client_socket.sendall(response)
        else:
            with open(abs_path, 'rb') as f:
                body = f.read()
            header = build_header(200, mime_type, len(body))
            client_socket.sendall(header + body)
    else:
        # Path doesn't exist → 404
        response_body = b'404 Not Found'
        response = build_header(404, 'text/plain', len(response_body)) + response_body
        client_socket.sendall(response)

    # Close client socket after handling request
    client_socket.close()

# Main server loop
def main():
    if len(sys.argv) < 2:
        print("Usage: python server.py <base_directory> [port]")
        sys.exit(1)

    base_dir = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(5)
    print(f"Server listening on port {port}...")

    # Initialize client_requests if needed
    global client_requests
    if not isinstance(client_requests, dict):
        client_requests = {}

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr}")

            # Create a new thread to handle the client request
            client_thread = threading.Thread(
                target=handle_request,
                args=(client_socket, base_dir),
                daemon=True  # This allows the thread to be terminated when main program exits
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()
