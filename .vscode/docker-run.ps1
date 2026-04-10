param(
    [Parameter(Mandatory = $true)]
    [string] $WorkspaceRoot
)

$ErrorActionPreference = 'Stop'
$envFile = Join-Path $WorkspaceRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing .env at $envFile"
}

$line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*(?i)base_url\s*=' } | Select-Object -First 1
if (-not $line) {
    throw 'BASE_URL not found in .env'
}

$baseUrl = ($line -split '=', 2)[1].Trim()
$baseUrl = $baseUrl -replace '127\.0\.0\.1', 'host.docker.internal'

# -e overrides value from --env-file for this variable only
# Без -t: иначе в Run Task / CI часто «input device is not a TTY». Для интерактива: docker exec …
& docker run --rm -i --env-file $envFile -e "BASE_URL=$baseUrl" ruz-client:local
