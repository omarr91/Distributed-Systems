param(
    [int[]]$MasterPorts = @(9001, 9002),
    [string]$WorkerUrls = "",
    [string]$NginxExePath = "nginx.exe",
    [string]$NginxWorkingDirectory = "",
    [ValidateSet("round_robin", "least_loaded", "load_aware")]
    [string]$SchedulerStrategy = "round_robin"
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MasterDir = Join-Path $RootDir "master"


Write-Host "Starting local master node(s)"
foreach ($port in $MasterPorts) {
    Write-Host "Starting master on http://localhost:$port"

    $command = "`$env:SCHEDULER_STRATEGY='$SchedulerStrategy'; uvicorn master:app --port $port"
    Start-Process powershell `
        -WorkingDirectory $MasterDir `
        -ArgumentList @(
            "-NoExit",
            "-Command",
            $command
        )
}

$startOptions = @{
    FilePath = $NginxExePath
}

if ($NginxWorkingDirectory) {
    $startOptions.WorkingDirectory = $NginxWorkingDirectory
}

Write-Host "Starting local NGINX: $NginxExePath"
if ($NginxWorkingDirectory) {
    Write-Host "NGINX working directory: $NginxWorkingDirectory"
}

Start-Process @startOptions

Write-Host ""
Write-Host "Local master/NGINX startup requested."
Write-Host "Scheduler strategy: $SchedulerStrategy"
Write-Host ""
Write-Host "Remote Linux workers must already be running and reachable from this machine."
