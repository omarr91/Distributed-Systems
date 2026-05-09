param(
    [int]$WorkerCount = 5,
    [int]$MasterCount = 2,
    [int]$FirstWorkerPort = 8001,
    [int]$FirstMasterPort = 9001,
    [int]$LoadBalancerPort = 80,
    [string]$WorkerImage = "distributed-ai-worker",
    [string]$MasterImage = "distributed-ai-master",
    [string]$NginxImage = "nginx:1.27-alpine",
    [string]$NetworkName = "distributed-ai-network",
    [string]$NginxConfigPath = "",
    [ValidateSet("round_robin", "least_loaded", "load_aware")]
    [string]$SchedulerStrategy = "load_aware",
    [switch]$UseDockerCache
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkerDir = Join-Path $RootDir "worker"
$MasterDir = Join-Path $RootDir "master"
$NginxDir = Join-Path $RootDir "nginx"

if (-not $NginxConfigPath) {
    $NginxConfigPath = Join-Path $NginxDir "nginx.conf"
}

if (-not (Test-Path $NginxDir)) {
    New-Item -ItemType Directory -Path $NginxDir | Out-Null
}

$existingNetwork = docker network ls --filter "name=^$NetworkName$" --format "{{.Name}}"
if (-not $existingNetwork) {
    Write-Host "Creating Docker network: $NetworkName"
    docker network create $NetworkName | Out-Null
}

Write-Host "Building worker Docker image: $WorkerImage"
if ($UseDockerCache) {
    docker build -t $WorkerImage $WorkerDir
}
else {
    docker build --no-cache -t $WorkerImage $WorkerDir
}

Write-Host "Building master Docker image: $MasterImage"
if ($UseDockerCache) {
    docker build -t $MasterImage $MasterDir
}
else {
    docker build --no-cache -t $MasterImage $MasterDir
}


Write-Host "Starting $WorkerCount worker container(s)"
for ($i = 1; $i -le $WorkerCount; $i++) {
    $hostPort = $FirstWorkerPort + $i - 1
    $containerName = "distributed-ai-worker$i"

    $existingContainer = docker ps -aq --filter "name=^/$containerName$"
    if ($existingContainer) {
        Write-Host "Removing existing container: $containerName"
        docker rm -f $containerName | Out-Null
    }

    Write-Host "Starting worker$i on http://localhost:$hostPort"
    docker run -d `
        --name $containerName `
        --network $NetworkName `
        --network-alias "worker$i" `
        --network-alias $containerName `
        -p "${hostPort}:8000" `
        -e "WORKER_NAME=worker$i" `
        $WorkerImage | Out-Null
}

$workerUrls = @()
for ($i = 1; $i -le $WorkerCount; $i++) {
    $workerUrls += "worker$i=http://distributed-ai-worker$i`:8000"
}
$workerUrlsEnv = $workerUrls -join ","

Write-Host "Starting $MasterCount master container(s)"
for ($i = 1; $i -le $MasterCount; $i++) {
    $hostPort = $FirstMasterPort + $i - 1
    $containerName = "distributed-ai-master$i"

    $existingContainer = docker ps -aq --filter "name=^/$containerName$"
    if ($existingContainer) {
        Write-Host "Removing existing container: $containerName"
        docker rm -f $containerName | Out-Null
    }

    Write-Host "Starting master$i on http://localhost:$hostPort"
    docker run -d `
        --name $containerName `
        --network $NetworkName `
        --network-alias "master$i" `
        --network-alias $containerName `
        -p "${hostPort}:8000" `
        -e "SCHEDULER_STRATEGY=$SchedulerStrategy" `
        -e "WORKER_URLS=$workerUrlsEnv" `
        $MasterImage | Out-Null
}

Write-Host "Waiting for master containers to be running"
for ($i = 1; $i -le $MasterCount; $i++) {
    $containerName = "distributed-ai-master$i"
    $isRunning = $false

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $state = docker inspect -f "{{.State.Running}}" $containerName 2>$null
        if ($state -eq "true") {
            $isRunning = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $isRunning) {
        Write-Host "Master container failed to stay running: $containerName"
        docker logs $containerName
        throw "Cannot start NGINX because $containerName is not running."
    }
}

Write-Host "Checking Docker DNS for master containers"
for ($i = 1; $i -le $MasterCount; $i++) {
    $containerName = "distributed-ai-master$i"
    docker run --rm --network $NetworkName $NginxImage getent hosts $containerName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker DNS could not resolve $containerName on network $NetworkName."
    }
}

if (-not (Test-Path $NginxConfigPath)) {
    Write-Host "NGINX config not found. Generating default config: $NginxConfigPath"

    $upstreamServers = for ($i = 1; $i -le $MasterCount; $i++) {
        "        server distributed-ai-master$i`:8000;"
    }

    $nginxConfig = @"
events {}

http {
    upstream master_nodes {
        least_conn;
$($upstreamServers -join "`n")
    }

    server {
        listen 80;

        location / {
            proxy_pass http://master_nodes;
            proxy_http_version 1.1;
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
            proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto `$scheme;
        }
    }
}
"@

    Set-Content -Path $NginxConfigPath -Value $nginxConfig -Encoding ASCII
}

$loadBalancerContainerName = "distributed-ai-nginx"
$existingLoadBalancer = docker ps -aq --filter "name=^/$loadBalancerContainerName$"
if ($existingLoadBalancer) {
    Write-Host "Removing existing container: $loadBalancerContainerName"
    docker rm -f $loadBalancerContainerName | Out-Null
}

Write-Host "Starting NGINX load balancer on http://localhost:$LoadBalancerPort"
docker run -d `
    --name $loadBalancerContainerName `
    --network $NetworkName `
    -p "${LoadBalancerPort}:80" `
    -v "${NginxConfigPath}:/etc/nginx/nginx.conf:ro" `
    $NginxImage | Out-Null

Start-Sleep -Seconds 2
$nginxRunning = docker inspect -f "{{.State.Running}}" $loadBalancerContainerName 2>$null
if ($nginxRunning -ne "true") {
    Write-Host "NGINX failed to start. Logs:"
    docker logs $loadBalancerContainerName
    throw "NGINX container is not running."
}

Write-Host ""
Write-Host "Cluster startup complete."
Write-Host "Load balancer: http://localhost:$LoadBalancerPort"
Write-Host "Scheduler strategy: $SchedulerStrategy"
Write-Host ""
Write-Host "Test through NGINX:"
Write-Host "  curl.exe -X POST http://localhost:$LoadBalancerPort/query -H `"Content-Type: application/json`" -d `"{\`"query\`":\`"hello\`"}`""
