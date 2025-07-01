FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install LibreOffice and try to install all useful font packages
RUN apt-get update && \
    for pkg in \
        libreoffice \
        ttf-mscorefonts-installer \
        fontconfig \
        fonts-liberation \
        fonts-dejavu \
        fonts-freefont-ttf \
        fonts-noto \
        fonts-noto-color-emoji \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
        fonts-roboto \
        fonts-ubuntu \
        fonts-droid-fallback \
    ; do \
        if apt-get install -y --no-install-recommends $pkg; then \
            echo "Installed $pkg"; \
        else \
            echo "Could not install $pkg (skipping)"; \
        fi; \
    done && \
    fc-cache -f -v && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your app
COPY . .

# (Optional) List all installed fonts in the build log
RUN fc-list

# Expose the Flask/gunicorn port
EXPOSE 5000

# Production entrypoint
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
