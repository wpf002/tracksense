FROM python:3.12-slim

WORKDIR /app

# System deps: udev/serial support for hardware reader mode
RUN apt-get update && apt-get install -y \
    lsof \
    usbutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Default: run the backend only (mock reader or hardware connects separately)
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
