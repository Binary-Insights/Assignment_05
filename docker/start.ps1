# Airflow Docker Stack Launcher for Windows
# This script sets up and starts the entire Docker environment with Airflow support

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 Airflow Docker Stack Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
}
catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
try {
    docker-compose --version | Out-Null
}
catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Navigate to script directory
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "📝 Step 1: Creating environment file..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ Environment file created from template" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  No .env.example found. Creating basic .env" -ForegroundColor Yellow
        $envContent = @"
AIRFLOW_HOME=/app/airflow_home
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=false
"@
        Set-Content -Path ".env" -Value $envContent
    }
}
else {
    Write-Host "✅ Environment file already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "🔨 Step 2: Building Docker images..." -ForegroundColor Yellow
docker-compose build --no-cache

Write-Host ""
Write-Host "⬆️  Step 3: Starting services..." -ForegroundColor Yellow
docker-compose up -d

Write-Host ""
Write-Host "⏳ Step 4: Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host ""
Write-Host "✅ All services are starting!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📊 Service Status:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🌐 Access Your Services:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔧 Airflow UI:" -ForegroundColor Green
Write-Host "   URL: http://localhost:8080" -ForegroundColor White
Write-Host "   Username: admin" -ForegroundColor White
Write-Host "   Password: admin" -ForegroundColor White
Write-Host ""
Write-Host "📡 FastAPI Documentation:" -ForegroundColor Green
Write-Host "   URL: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "📊 Streamlit Dashboard:" -ForegroundColor Green
Write-Host "   URL: http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "🗄️  PostgreSQL Database:" -ForegroundColor Green
Write-Host "   Host: localhost" -ForegroundColor White
Write-Host "   Port: 5432" -ForegroundColor White
Write-Host "   Username: airflow" -ForegroundColor White
Write-Host "   Password: airflow" -ForegroundColor White
Write-Host "   Database: airflow" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📋 Useful Commands:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "# View logs" -ForegroundColor Gray
Write-Host "docker-compose logs -f airflow-webserver" -ForegroundColor White
Write-Host ""
Write-Host "# List DAGs" -ForegroundColor Gray
Write-Host "docker exec pe-dashboard-airflow-scheduler airflow dags list" -ForegroundColor White
Write-Host ""
Write-Host "# Stop services" -ForegroundColor Gray
Write-Host "docker-compose down" -ForegroundColor White
Write-Host ""
Write-Host "# Stop and remove all data" -ForegroundColor Gray
Write-Host "docker-compose down -v" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✨ Ready to go! Visit http://localhost:8080" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
