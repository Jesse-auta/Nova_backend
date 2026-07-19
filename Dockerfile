# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app


# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt



# Copy application code
COPY . .


# Expose port (tells Railway which port to listen on)
EXPOSE 8000


# Health check (Railway uses this to verify app is alive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"


# Run the app
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
