import sys
import os
import socket
from urllib.parse import urlparse

def save_file(directory, filename, data):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"Saved {filename} to {directory}")

def main():
    if len(sys.argv) != 5:
        print("Usage: python client.py server_host server_port url_path directory")
        sys.exit(1)

    server_host = sys.argv[1]
    server_port = int(sys.argv[2])
    url_path = sys.argv[3]
    save_dir = sys.argv[4]

    # Ensure path starts with /
    if not url_path.startswith('/'):
        url_path = '/' + url_path

    # Create TCP connection
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((server_host, server_port))
        request = f"GET {url_path} HTTP/1.1\r\nHost: {server_host}\r\nConnection: close\r\n\r\n"
        s.sendall(request.encode())

        # Receive response
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk

    # Separate headers and body
    try:
        header_data, body = response.split(b"\r\n\r\n", 1)
    except ValueError:
        print("Invalid response from server")
        sys.exit(1)

    headers = header_data.decode().split("\r\n")
    content_type = None
    for h in headers:
        if h.lower().startswith("content-type:"):
            content_type = h.split(":", 1)[1].strip()
            break

    # Decide what to do based on content type
    filename = os.path.basename(url_path)
    if not filename:  # path ends with / → directory listing
        print(body.decode(errors='ignore'))
    elif content_type and ("text/html" in content_type):
        print(body.decode(errors='ignore'))
    elif content_type and ("application/pdf" in content_type or "image/png" in content_type):
        save_file(save_dir, filename, body)
    else:
        print(f"Unknown content type: {content_type}, printing raw response")
        print(body.decode(errors='ignore'))

if __name__ == "__main__":
    main()
