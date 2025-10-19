# Use a lightweight Python image
FROM python:3.13-slim

# Set working directory inside the container
WORKDIR /app

# Copy the server script and content
COPY server.py .
COPY content ./content

# Expose the port the server uses
EXPOSE 8000

# Run the server with the content folder as argument
CMD ["python", "server.py", "content", "8000"]

