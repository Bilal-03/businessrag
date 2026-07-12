# Dockerfile for deploying the FastAPI backend to Hugging Face Spaces
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY --chown=user . .

# Hugging Face Spaces expose port 7860 by default
EXPOSE 7860

# Run the FastAPI server
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
