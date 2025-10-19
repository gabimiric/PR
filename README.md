# Network Programming

### Lab 1
### Miricinschi Gabriel

## To start container
```
docker-compose up --build -d
```

## Contents of source directory
```
server.py
client.py
Dockerfile
docker-compose.yml
index.html
content/
  ├─ books/
  │ ├─ book1.pdf
  │ └─ book2.pdf
  ├─ labs/
  │ ├─ Labs.pdf
  │ └─ image.png
  └─ images/
  └─ cover.png
```

## Docker compose file + dockerfile
```yml
version: '3.8'
services:
  pdf-server:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./content:/app/content
```
```yml
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
```

## Command that runs the server inside the container
```
 python server.py content 8000
```

## Contents of the served directory
```
content/
  ├─ books/
  │   ├─ book1.pdf
  │   └─ book2.pdf
  ├─ labs/
  │   ├─ Labs.pdf
  │   └─ image.png
  └─ images/
      └─ cover.png
```

## Requests of 4 files in the browser
### Inexistent file (404)
<img width="1234" height="933" alt="image" src="https://github.com/user-attachments/assets/c8aa09b6-e673-4324-a0d5-a8ef481d703b" />

### HTML file with image
<img width="1234" height="938" alt="image" src="https://github.com/user-attachments/assets/341ff60f-b243-4903-ac1b-e49bf1f84f90" />

### PDF file
<img width="1235" height="937" alt="image" src="https://github.com/user-attachments/assets/574d1d00-2689-466e-ac1e-666ef2b64bf0" />

### PNG file
<img width="1234" height="936" alt="image" src="https://github.com/user-attachments/assets/adf0e1a5-1815-44e7-b6d6-41bc0461463a" />

## Client Run + Output and saved files
<img width="752" height="748" alt="image" src="https://github.com/user-attachments/assets/748a5030-7db1-40c8-8512-f1b38f376106" />
<img width="831" height="39" alt="image" src="https://github.com/user-attachments/assets/a365ec8c-5845-4e33-8d40-ab28556db9ff" />
<img width="303" height="360" alt="image" src="https://github.com/user-attachments/assets/d88aaee7-c5da-436e-b6e6-da3d881c4ffa" />

## Directory listing generated page
### Raw directory sublist
<img width="271" height="127" alt="image" src="https://github.com/user-attachments/assets/5359312b-83da-43d9-868d-78b824d78589" />

### All sublists injected into main index
<img width="360" height="612" alt="image" src="https://github.com/user-attachments/assets/98c203fe-e0f9-42f6-9372-359fd4065554" />



