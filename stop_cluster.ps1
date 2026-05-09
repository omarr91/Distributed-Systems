param(
    [int]$WorkerCount = 5,
    [int]$MasterCount = 2,
    [string]$NetworkName = "distributed-ai-network",
    [switch]$RemoveNetwork
)

$ErrorActionPreference = "Stop"

$containers = @("distributed-ai-nginx")

for ($i = 1; $i -le $MasterCount; $i++) {
    $containers += "distributed-ai-master$i"
}

for ($i = 1; $i -le $WorkerCount; $i++) {
    $containers += "distributed-ai-worker$i"
}

foreach ($containerName in $containers) {
    $existingContainer = docker ps -aq --filter "name=^/$containerName$"
    if ($existingContainer) {
        Write-Host "Removing container: $containerName"
        docker rm -f $containerName | Out-Null
    }
    else {
        Write-Host "Container not found: $containerName"
    }
}

if ($RemoveNetwork) {
    $existingNetwork = docker network ls --filter "name=^$NetworkName$" --format "{{.Name}}"
    if ($existingNetwork) {
        Write-Host "Removing Docker network: $NetworkName"
        docker network rm $NetworkName | Out-Null
    }
    else {
        Write-Host "Docker network not found: $NetworkName"
    }
}

Write-Host "Cluster containers stopped."
