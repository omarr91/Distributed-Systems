param(
    [int]$WorkerCount = 3,
    [int]$FirstWorkerPort = 8001,
    [int[]]$MasterPorts = @(9001, 9002),
    [string]$WorkerImage = "worker-image"
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkerDir = Join-Path $RootDir "worker"
$MasterDir = Join-Path $RootDir "master"

Write-Host "Building worker Docker image: $WorkerImage"
docker build -t $WorkerImage $WorkerDir

Write-Host "Starting $WorkerCount worker container(s)"
for ($i = 1; $i -le $WorkerCount; $i++) {
    $hostPort = $FirstWorkerPort + $i - 1
    $workerName = "worker$i"
    $containerName = "distributed-ai-$workerName"

    $existingContainer = docker ps -aq --filter "name=^/$containerName$"
    if ($existingContainer) {
        Write-Host "Removing existing container: $containerName"
        docker rm -f $containerName | Out-Null
    }

    Write-Host "Starting $workerName on http://localhost:$hostPort"
    docker run -d `
        --name $containerName `
        -p "${hostPort}:8000" `
        -e "WORKER_NAME=$workerName" `
        $WorkerImage | Out-Null
}

Write-Host "Starting master node(s)"
foreach ($port in $MasterPorts) {
    Write-Host "Starting master on http://localhost:$port"
    Start-Process powershell `
        -WorkingDirectory $MasterDir `
        -ArgumentList @(
            "-NoExit",
            "-Command",
            "python -m uvicorn master:app --port $port"
        )
}

Write-Host ""
Write-Host "Cluster startup requested."
Write-Host "Workers:"
for ($i = 1; $i -le $WorkerCount; $i++) {
    $hostPort = $FirstWorkerPort + $i - 1
    Write-Host "  http://localhost:$hostPort"
}
Write-Host "Masters:"
foreach ($port in $MasterPorts) {
    Write-Host "  http://localhost:$port"
}
Write-Host ""
Write-Host "Test through a master:"
Write-Host '  curl.exe -X POST http://localhost:9001/query -H "Content-Type: application/json" -d "{\"query\":\"hello\"}"'
Write-Host ""
Write-Host "Stop worker containers:"
Write-Host '  docker rm -f distributed-ai-worker1 distributed-ai-worker2 distributed-ai-worker3'