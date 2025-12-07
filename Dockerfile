FROM python:3.10-slim

WORKDIR /app
COPY . /app

# Install requirements if exists
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

EXPOSE 8501

# Default command launches Streamlit UI; override with --entrypoint for CLI
CMD ["python", "-m", "streamlit", "run", "app/pages/語意圖譜.py", "--server.port=8501", "--server.address=0.0.0.0"]
