import os
import sys
import socket
import mimetypes

# Usage: python server.py <directory> <port>

# Build HTTP response headers
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

# Recursively generate HTML for all files/folders under a directory
def generate_directory_listing(directory, rel_path=""):
    items = sorted(os.listdir(directory))
    html = []

    for item in items:
        if item == "index.html":
            continue # Skip index.html from the listing

        full_path = os.path.join(directory, item)
        display_name = item + ('/' if os.path.isdir(full_path) else '')
        link = os.path.join('/', rel_path, item).replace('\\', '/')

        if os.path.isdir(full_path):
            # Use <details> for collapsible folders
            html.append(f'<li><details><summary>{display_name}</summary>')
            html.append(generate_directory_listing(full_path, os.path.join(rel_path, item)))
            html.append('</details></li>')
        else:
            # Only include files of these types
            if item.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.gif')):
                html.append(f'<li><a href="{link}">{display_name}</a></li>')

    return '\n'.join(html) # Return as a single string

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

    # Normalize path to avoid path traversal
    rel_path = path.lstrip('/')
    abs_path = os.path.abspath(os.path.join(base_dir, rel_path))
    base_dir_abs = os.path.abspath(base_dir)

    # Ensure path is within base_dir
    if not abs_path.startswith(os.path.abspath(base_dir)):
        # Requested path is outside base_dir → return 404
        response_body = b'404 Not Found'
        response = build_header(404, 'text/plain', len(response_body)) + response_body
        client_socket.sendall(response)
        client_socket.close()
        return

    # Serve the main index page if root is requested
    if path == "/" or path == "":
        serve_index_page(client_socket, base_dir)
        return

    # Normalize requested path to prevent path traversal
    if os.path.isdir(abs_path):
        ## Return a recursive directory listing for folders
        body = generate_directory_listing(abs_path, rel_path).encode('utf-8')
        header = build_header(200, 'text/html; charset=utf-8', len(body))
        client_socket.sendall(header + body)

    elif os.path.isfile(abs_path):
        # Serve the file with the correct MIME type
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
