FROM apache/airflow:2.10.4-python3.11

WORKDIR /app

# Install additional system dependencies if needed
USER root
RUN apt-get update && apt-get install -y \
    git \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libx11-6 \
    libxss1 \
    libappindicator1 \
    xdg-utils \
    fonts-liberation \
    libnss3 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for chromedriver compatibility
RUN ln -s /usr/bin/chromium-driver /usr/bin/chromedriver || true

USER airflow

# Install additional Python requirements from parent directory
COPY requirements.txt /app/requirements.txt
# Pin SQLAlchemy to version compatible with Airflow 2.10.4 and exclude it from requirements
RUN pip install --no-cache-dir "sqlalchemy<2.0.0" && \
    grep -v "sqlalchemy" /app/requirements.txt > /tmp/requirements_no_sql.txt && \
    pip install --no-cache-dir -r /tmp/requirements_no_sql.txt

# Copy application code from parent directory
COPY src /app/src
COPY data /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__CORE__UNIT_TEST_MODE=false
ENV AIRFLOW__CORE__DAGS_FOLDER=/app/src/dags
ENV AIRFLOW__CORE__EXECUTOR=LocalExecutor
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV CHROME_BIN=/usr/bin/chromium

# Default command - will be overridden by docker-compose
CMD ["airflow", "version"]
