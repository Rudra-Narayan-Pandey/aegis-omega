# Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install standard dependencies
RUN pip install --no-cache-dir fastapi uvicorn numpy

# Copy the proxy gateway code we wrote earlier
COPY services/aegis-proxy-gateway/app /app/

# Create a non-root user to prevent container escape vulnerabilities
RUN adduser --disabled-password --gecos '' aegis-user
USER aegis-user

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# Add this near the end of your Dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1
