FROM python:3.13-slim

WORKDIR /app

# Install system dependencies, including curl for the script
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    libffi-dev \
    libssl-dev \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies
RUN uv sync

# Copy the wait script and ensure it is executable
# COPY run/wait-for-db.sh /usr/local/bin/wait-for-db.sh
# RUN chmod +x /usr/local/bin/wait-for-db.sh

# Copy the rest of the code
COPY . .

EXPOSE 8000

# Start FastAPI app
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
