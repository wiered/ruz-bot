param(
    [Parameter(Mandatory = $true)]
    [string] $WorkspaceRoot,

    [string] $Image = 'ruzbot:local'
)

$ErrorActionPreference = 'Stop'
$envFile = Join-Path $WorkspaceRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing .env at $envFile"
}

$botLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*(?i)bot_token\s*=' } | Select-Object -First 1
if (-not $botLine) {
    throw 'BOT_TOKEN not found in .env'
}

$baseLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^\s*(?i)base_url\s*=' } | Select-Object -First 1
if (-not $baseLine) {
    throw 'BASE_URL not found in .env'
}

$baseUrl = ($baseLine -split '=', 2)[1].Trim()
$baseUrl = $baseUrl -replace '127\.0\.0\.1', 'host.docker.internal'

# -e overrides value from --env-file for this variable only
# Без -t: иначе в Run Task / CI часто «input device is not a TTY». Для интерактива: docker exec …
& docker run --rm -i --env-file $envFile -e "BASE_URL=$baseUrl" $Image
