FROM python:3.9-slim

WORKDIR /app

# Install FastAPI and Uvicorn
RUN pip install fastapi uvicorn

# Copy the frontend files and the server script
COPY index.html main.py ./
COPY styles/ ./styles/
COPY script/ ./script/
# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["python", "main.py"]