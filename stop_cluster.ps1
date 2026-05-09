param(
    [string]$NginxExePath = "nginx.exe",
    [string]$NginxWorkingDirectory = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

Write-Host "Stopping local master node process(es)"
Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*uvicorn master:app*" -and
        $_.CommandLine -notlike "*Where-Object*"
    } |
    ForEach-Object {
        Write-Host "Stopping master process PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }

$stopOptions = @{
    FilePath = $NginxExePath
    ArgumentList = @("-s", "stop")
    Wait = $true
}

if ($NginxWorkingDirectory) {
    $stopOptions.WorkingDirectory = $NginxWorkingDirectory
}

try {
    Write-Host "Stopping local NGINX: $NginxExePath -s stop"
    Start-Process @stopOptions
}
catch {
    if (-not $Force) {
        throw
    }

    Write-Host "Graceful NGINX stop failed. Force-stopping nginx processes."
    Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force
}

Write-Host "Local master/NGINX processes stopped."
