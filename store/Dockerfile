# Use the official Python image as the base image
FROM python:3.9-slim
# Set the working directory inside the container
WORKDIR /app
# Install build dependencies needed for compiling packages from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*
# Copy the requirements.txt file and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt
# Copy the entire application into the container
COPY . .
# Run the main.py script inside the container when it starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]