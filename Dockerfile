FROM python:3.11-slim

# Set non-interactive to prevent TTF install prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install LibreOffice, MS Core Fonts, and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        ttf-mscorefonts-installer \
        fontconfig \
        fonts-liberation \
        fonts-dejavu \
        fonts-freefont-ttf \
        fonts-noto \
        fonts-roboto \
        fonts-ubuntu \
        fonts-droid-fallback \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        fonts-noto-color-emoji \
        python3-pip \
        build-essential \
        gcc \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && fc-cache -f -v \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy all app source code
COPY . .

# Expose port 5000
EXPOSE 5000

# Start with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
