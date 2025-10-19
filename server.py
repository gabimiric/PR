import os
import sys
import socket
import mimetypes

# Usage: python server.py <directory> <port>

def build_header(status_code, content_type=None, content_length=0):
    status_messages = {
        200: "OK",
        404: "Not Found"
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

def generate_directory_listing(directory, rel_path):
    items = os.listdir(directory)
    html = ["<html><body>", f"<h2>Index of /{rel_path}</h2>", "<ul>"]

    # Parent directory link
    if rel_path != "":
        parent_path = os.path.dirname(rel_path.rstrip('/'))
        html.append(f'<li><a href="/{parent_path}">..</a></li>')

    for item in items:
        full_path = os.path.join(directory, item)
        display_name = item + ('/' if os.path.isdir(full_path) else '')
        link = os.path.join('/', rel_path, item).replace('\\', '/')
        html.append(f'<li><a href="{link}">{display_name}</a></li>')

    html.append("</ul></body></html>")
    return '\n'.join(html).encode('utf-8')

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

    # Debug prints
    print("Raw request:", request.decode())
    print("Requested path:", path)

    if method != "GET":
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

    # Normalize path to avoid path traversal
    rel_path = path.lstrip('/')
    abs_path = os.path.normpath(os.path.join(base_dir, rel_path))

    # Ensure path is within base_dir
    if not abs_path.startswith(os.path.abspath(base_dir)):
        response_body = b'404 Not Found'
        response = build_header(404, 'text/plain', len(response_body)) + response_body
        client_socket.sendall(response)
        client_socket.close()
        return

    if os.path.isdir(abs_path):
        # Serve index.html if it exists
        index_file = os.path.join(abs_path, "index.html")
        if os.path.isfile(index_file):
            with open(index_file, 'rb') as f:
                body = f.read()
            header = build_header(200, 'text/html; charset=utf-8', len(body))
            client_socket.sendall(header + body)
        else:
            # Otherwise generate directory listing
            body = generate_directory_listing(abs_path, rel_path)
            header = build_header(200, 'text/html; charset=utf-8', len(body))
            client_socket.sendall(header + body)
    elif os.path.isfile(abs_path):
        mime_type, _ = mimetypes.guess_type(abs_path)
        if mime_type not in ['text/html', 'image/png', 'application/pdf']:
            response_body = b'404 Not Found'
            response = build_header(404, 'text/plain', len(response_body)) + response_body
            client_socket.sendall(response)
        else:
            with open(abs_path, 'rb') as f:
                body = f.read()
            header = build_header(200, mime_type, len(body))
            client_socket.sendall(header + body)
    else:
        response_body = b'404 Not Found'
        response = build_header(404, 'text/plain', len(response_body)) + response_body
        client_socket.sendall(response)

    client_socket.close()

def main():
    if len(sys.argv) != 3:
        print("Usage: python server.py <directory> <port>")
        sys.exit(1)

    base_dir = sys.argv[1]
    port = int(sys.argv[2])

    if not os.path.isdir(base_dir):
        print(f"Error: {base_dir} is not a directory")
        sys.exit(1)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(1)

    print(f"Serving {base_dir} on port {port}...")

    try:
        while True:
            client_socket, client_addr = server_socket.accept()
            print(f"Connection from {client_addr}")
            handle_request(client_socket, base_dir)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()
