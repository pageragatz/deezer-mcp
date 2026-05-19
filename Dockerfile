FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install -r requirements.txt --system

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "server.py"]