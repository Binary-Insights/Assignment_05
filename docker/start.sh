#!/bin/bash

# Airflow Docker Stack Launcher
# This script sets up and starts the entire Docker environment with Airflow support

set -e

echo "========================================"
echo "🚀 Airflow Docker Stack Launcher"
echo "========================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Navigate to docker directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📝 Step 1: Creating environment file..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Environment file created from template"
    else
        echo "⚠️  No .env.example found. Creating basic .env"
        cat > .env << EOF
AIRFLOW_HOME=/app/airflow_home
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=false
EOF
    fi
else
    echo "✅ Environment file already exists"
fi

echo ""
echo "🔨 Step 2: Building Docker images..."
docker-compose build --no-cache

echo ""
echo "⬆️  Step 3: Starting services..."
docker-compose up -d

echo ""
echo "⏳ Step 4: Waiting for services to be ready..."
sleep 10

echo ""
echo "✅ All services are starting!"
echo ""
echo "========================================"
echo "📊 Service Status:"
echo "========================================"
docker-compose ps

echo ""
echo "========================================"
echo "🌐 Access Your Services:"
echo "========================================"
echo ""
echo "🔧 Airflow UI:"
echo "   URL: http://localhost:8080"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "📡 FastAPI Documentation:"
echo "   URL: http://localhost:8000/docs"
echo ""
echo "📊 Streamlit Dashboard:"
echo "   URL: http://localhost:8501"
echo ""
echo "🗄️  PostgreSQL Database:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Username: airflow"
echo "   Password: airflow"
echo "   Database: airflow"
echo ""
echo "========================================"
echo "📋 Useful Commands:"
echo "========================================"
echo ""
echo "# View logs"
echo "docker-compose logs -f airflow-webserver"
echo "docker-compose logs -f airflow-scheduler"
echo ""
echo "# Execute commands in containers"
echo "docker exec pe-dashboard-airflow-scheduler airflow dags list"
echo ""
echo "# Stop services"
echo "docker-compose down"
echo ""
echo "# Stop and remove all data"
echo "docker-compose down -v"
echo ""
echo "========================================"
echo "✨ Ready to go! Visit http://localhost:8080"
echo "========================================"
