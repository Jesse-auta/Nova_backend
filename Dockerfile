# Use official Python runtime as base image
FROM python:3.11-slim

"""
Why Python 3.11?
- Latest stable, good performance
- -slim variant is smaller (no unnecessary packages)
"""

# Set working directory in container
WORKDIR /app

"""
All commands after this run inside /app directory in the container
"""

# Copy requirements file
COPY requirements.txt .

"""
COPY (local file) (container location)
Copies requirements.txt from your machine into the container
"""

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

"""
RUN executes a command during build
pip install installs all packages from requirements.txt
--no-cache-dir saves space (don't store pip cache in image)
"""

# Copy application code
COPY . .

"""
Copy entire app folder into container
Now the container has all our code
"""

# Expose port (tells Railway which port to listen on)
EXPOSE 8000

"""
EXPOSE 8000 tells Railway: "This app listens on port 8000"
Railway will forward external traffic to this port
"""

# Health check (Railway uses this to verify app is alive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

"""
Why health check?
- Railway pings /health every 30 seconds
- If it fails 3 times, Railway restarts the app
- Ensures app stays alive
"""

# Run the app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

"""
CMD is the default command when container starts
python -m uvicorn runs the FastAPI app
--host 0.0.0.0 listens on all network interfaces (required for Railway)
--port 8000 runs on port 8000
app.main:app means "in app/main.py, use the 'app' object"
"""