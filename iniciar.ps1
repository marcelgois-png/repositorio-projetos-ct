param(
    [int]$Porta = 8000,
    [switch]$AbrirNavegador,
    [switch]$Docker
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Repositório de Projetos Arquitetônicos CT/UFPB" -ForegroundColor Cyan
Write-Host "Diretório: $PSScriptRoot"
Write-Host ""

if ($Docker) {
    Write-Host "Iniciando com Docker Compose e MySQL..." -ForegroundColor Yellow
    docker compose up --build
    exit $LASTEXITCODE
}

Write-Host "Iniciando modo local de verificação com SQLite..." -ForegroundColor Yellow
$env:DJANGO_USE_SQLITE = "1"

Write-Host "Aplicando migrations..."
python manage.py migrate --noinput

Write-Host "Garantindo categorias iniciais..."
python manage.py seed_initial_data

$adminInfo = python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); print(User.objects.filter(username='admin').exists())"
$adminExists = ($adminInfo | Select-Object -Last 1).Trim()

if ($adminExists -ne "True") {
    Write-Host ""
    Write-Host "Usuário admin ainda não existe." -ForegroundColor Yellow
    Write-Host "Para criar, abra outro PowerShell nesta pasta e rode:"
    Write-Host '  $env:DJANGO_USE_SQLITE="1"'
    Write-Host '  python manage.py seed_initial_data --create-admin --username admin'
    Write-Host ""
}

$url = "http://127.0.0.1:$Porta/"
Write-Host ""
Write-Host "Servidor local:" -ForegroundColor Green
Write-Host "  $url"
Write-Host ""
Write-Host "Pressione Ctrl+C para parar o servidor."
Write-Host ""

if ($AbrirNavegador) {
    Start-Process $url
}

python manage.py runserver "127.0.0.1:$Porta"
