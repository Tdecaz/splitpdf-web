FROM python:3.11-slim

# Install LibreOffice and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        python3-pip \
        build-essential \
        gcc \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy all app source code
COPY . .

# Expose port 5000 (the Flask default)
EXPOSE 5000

# Start with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
