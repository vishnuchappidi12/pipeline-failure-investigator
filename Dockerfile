FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set python path so imports work correctly
ENV PYTHONPATH=/app

# Expose ports for both API and UI
EXPOSE 8000
EXPOSE 8501
