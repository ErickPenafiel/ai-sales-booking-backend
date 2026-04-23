# Loads .env into environment and starts uvicorn using API_PORT
Set-StrictMode -Version Latest
if (-Not (Test-Path -Path ".env")) {
    Write-Host "No .env found. Copy .env.example to .env and update values." -ForegroundColor Yellow
}

# Load .env (simple parser)
Get-Content .env -ErrorAction SilentlyContinue | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $parts = $line -split "=", 2
    if ($parts.Count -ge 2) {
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim("\"")
        Set-Item -Path Env:$name -Value $value
    }
}

$port = $Env:API_PORT
if (![int]::TryParse($port, [ref]0)) {
    $port = 8010
}

Write-Host "Starting uvicorn on port $port..."
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port $port
