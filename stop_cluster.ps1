param(
    [int[]]$MasterPorts = @(9001, 9002),
    [string]$NetworkName = "distributed-ai-network",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# ── Helper ────────────────────────────────────────────────────────────────

function Remove-Container {
    param([string]$Name)
    $existing = docker ps -aq --filter "name=^/${Name}$"
    if ($existing) {
        Write-Host "Stopping and removing container: $Name"
        docker rm -f $Name | Out-Null
        if ($LASTEXITCODE -ne 0) {
            if ($Force) { Write-Warning "Failed to remove $Name, continuing..." }
            else        { throw "Failed to remove container: $Name" }
        }
    } else {
        Write-Host "Container not found, skipping: $Name"
    }
}

# ── Stop nginx ────────────────────────────────────────────────────────────

Remove-Container "distributed-ai-nginx"

# ── Stop master containers ────────────────────────────────────────────────

foreach ($port in $MasterPorts) {
    Remove-Container "distributed-ai-master-$port"
}

# ── Stop worker containers (local ones if any) ────────────────────────────

$workerContainers = docker ps -aq --filter "name=^/distributed-ai-worker"
if ($workerContainers) {
    Write-Host "Stopping and removing worker containers..."
    $workerContainers | ForEach-Object {
        $name = docker inspect --format "{{.Name}}" $_ | TrimStart("/")
        Write-Host "  Removing worker container: $name"
    }
    docker rm -f ($workerContainers -join " ") | Out-Null
} else {
    Write-Host "No worker containers found, skipping."
}

# ── Remove Docker network ─────────────────────────────────────────────────

$existingNetwork = docker network ls --filter "name=^${NetworkName}$" -q
if ($existingNetwork) {
    Write-Host "Removing Docker network: $NetworkName"
    docker network rm $NetworkName | Out-Null
    if ($LASTEXITCODE -ne 0) {
        if ($Force) { Write-Warning "Failed to remove network $NetworkName, continuing..." }
        else        { throw "Failed to remove network: $NetworkName" }
    }
} else {
    Write-Host "Network not found, skipping: $NetworkName"
}

# ── Stop any leftover uvicorn processes (non-Docker) ─────────────────────

$uvicornProcs = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*uvicorn master:app*" -and
        $_.CommandLine -notlike "*Where-Object*"
    }

if ($uvicornProcs) {
    Write-Host "Stopping leftover uvicorn process(es)..."
    $uvicornProcs | ForEach-Object {
        Write-Host "  Stopping PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
} else {
    Write-Host "No leftover uvicorn processes found."
}

# ── Summary ───────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Teardown complete."
Write-Host ""
Write-Host "Verify nothing is left:"
Write-Host "  docker ps -a --filter 'name=distributed-ai'"
Write-Host "  docker network ls --filter 'name=$NetworkName'"