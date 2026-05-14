param(
    [int[]]$MasterPorts = @(9001, 9002),
    [int]$WorkerCount = 5,
    [int]$WorkerStartPort = 8001,
    [string]$WorkerImage = "worker-image",
    [string]$NginxImage = "nginx:latest",
    [string]$NginxConfigPath = ".\nginx\nginx.conf",
    [string]$MasterImage = "master-image",
    [ValidateSet("round_robin", "least_loaded", "load_aware")]
    [string]$SchedulerStrategy = "load_aware",
    [string]$NetworkName = "distributed-ai-network"
)

$ErrorActionPreference = "Stop"

$RootDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$MasterDir = Join-Path $RootDir "master"
$NginxDir  = Join-Path $RootDir "nginx"
$WorkerDir = Join-Path $RootDir "worker"

# ── Network ───────────────────────────────────────────────────────────────

$existingNetwork = docker network ls --filter "name=^${NetworkName}$" -q
if (-not $existingNetwork) {
    Write-Host "Creating Docker network: $NetworkName"
    docker network create $NetworkName
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Docker network" }
}

# ── Workers ──────────────────────────────────────────────────────────
$WorkerPorts = @()

for ($i = 0; $i -lt $WorkerCount; $i++) {
    $WorkerPorts += ($WorkerStartPort + $i)
}

Write-Host "Building worker image: $WorkerImage"

docker build -t $WorkerImage $WorkerDir

if ($LASTEXITCODE -ne 0) {
    throw "Worker docker build failed"
}

foreach ($port in $WorkerPorts) {

    $containerName = "distributed-ai-worker-$port"

    $existing = docker ps -aq --filter "name=^/${containerName}$"

    if ($existing) {
        Write-Host "Removing existing worker container: $containerName"
        docker rm -f $containerName | Out-Null
    }

    Write-Host "Starting worker on http://localhost:$port"

    docker run -d `
        --name $containerName `
        --network $NetworkName `
        --gpus all `
        -p "${port}:8000" `
        -e "WORKER_NAME=worker-$port" `
        $WorkerImage | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start worker on port $port"
    }
}

$ComputedWorkerUrls = ""
for ($i = 0; $i -lt $WorkerPorts.Count; $i++) {
    $port = $WorkerPorts[$i]
    if ($i -gt 0) { $ComputedWorkerUrls += "," }
    $ComputedWorkerUrls += "http://distributed-ai-worker-${port}:8000"
}

Write-Host $ComputedWorkerUrls
# ── Master nodes ──────────────────────────────────────────────────────────

Write-Host "Building master image: $MasterImage"
docker build -t $MasterImage $MasterDir
if ($LASTEXITCODE -ne 0) { throw "Master docker build failed" }

foreach ($port in $MasterPorts) {
    $containerName = "distributed-ai-master-$port"

    $existing = docker ps -aq --filter "name=^/${containerName}$"
    if ($existing) {
        Write-Host "Removing existing container: $containerName"
        docker rm -f $containerName | Out-Null
    }

    Write-Host "Starting master on http://localhost:$port"
    docker run -d `
        --name $containerName `
        --network $NetworkName `
        -p "${port}:8000" `
        -e "SCHEDULER_STRATEGY=$SchedulerStrategy" `
        -e "WORKER_URLS=$ComputedWorkerUrls" `
        $MasterImage | Out-Null

    if ($LASTEXITCODE -ne 0) { throw "Failed to start master on port $port" }
}

# ── Nginx ─────────────────────────────────────────────────────────────────

$nginxContainerName = "distributed-ai-nginx"

$existing = docker ps -aq --filter "name=^/${nginxContainerName}$"
if ($existing) {
    Write-Host "Removing existing nginx container"
    docker rm -f $nginxContainerName | Out-Null
}

# Use custom nginx.conf if provided, otherwise use the one in ./nginx/
$resolvedNginxConfig = if ($NginxConfigPath) {
    $NginxConfigPath
} else {
    Join-Path $NginxDir "nginx.conf"
}

if (-not (Test-Path $resolvedNginxConfig)) {
    throw "nginx.conf not found at: $resolvedNginxConfig"
}

# Convert to absolute path for Docker volume mount
$resolvedNginxConfig = Resolve-Path $resolvedNginxConfig

Write-Host "Starting nginx container"
docker run -d `
    --name $nginxContainerName `
    --network $NetworkName `
    -p "80:80" `
    -v "${resolvedNginxConfig}:/etc/nginx/nginx.conf:ro" `
    $NginxImage | Out-Null

if ($LASTEXITCODE -ne 0) { throw "Failed to start nginx container" }

# ── Summary ───────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Cluster startup complete."
Write-Host "Scheduler strategy: $SchedulerStrategy"
Write-Host ""
Write-Host "Masters:"
foreach ($port in $MasterPorts) {
    Write-Host "  http://localhost:$port"
}
Write-Host ""
Write-Host "Workers:"
foreach ($port in $WorkerPorts) {
    Write-Host "  http://localhost:$port"
}
Write-Host "Nginx:   http://localhost:80"
Write-Host ""
Write-Host "Test through nginx:"
Write-Host '  curl.exe -X POST http://localhost/query -H "Content-Type: application/json" -d "{\"query\":\"hello\"}"'
Write-Host ""
Write-Host "Stop all containers:"
$allContainers = @("distributed-ai-nginx") + ($MasterPorts | ForEach-Object { "distributed-ai-master-$_" })
Write-Host "  docker rm -f $($allContainers -join ' ')"