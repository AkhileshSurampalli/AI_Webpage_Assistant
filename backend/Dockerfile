# A slim Python base image to keep the container small
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy and install dependencies first (Docker layer caching optimization -
# this layer only rebuilds if requirements.txt changes, not on every code change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY main.py .

# Expose the port FastAPI will run on
EXPOSE 8000

# Run as a non-root user for security best practice
RUN useradd -m appuser
USER appuser

# Command to run when the container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]