$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$exe = Join-Path $PSScriptRoot "dist\ProxyChat.exe"
if (-not (Test-Path $exe)) {
    throw "Missing $exe. Build ProxyChat.exe first (.\build_exe.ps1)."
}

# Surumun tek kaynagi apps\proxychat\version.py; installer kayit defterine
# ayni degeri yazsin. (Eskiden ui.py'deydi; acilis ekrani agir ice
# aktarmalardan once gosterilebilsin diye ayri dosyaya tasindi.)
$versionSource = Get-Content (Join-Path $PSScriptRoot "apps\proxychat\version.py") -Raw
# (?m)^ : satir basi. Aciklama metnindeki ornek bir satir surum sanilmasin.
if ($versionSource -notmatch '(?m)^APP_VERSION\s*=\s*"([^"]+)"') {
    throw "APP_VERSION could not be read from apps\proxychat\version.py."
}
$appVersion = $Matches[1]
Write-Host "ProxyChat version: $appVersion"

# Exe kaynaktan eskiyse (ornegin calisan bir ProxyChat.exe dosyayi kilitledigi
# icin son derleme basarisiz olduysa) installer eski programi yeni surum
# numarasiyla paketlerdi. Bu bir kez oldu; artik durduruluyor.
$newestSource = Get-ChildItem (Join-Path $PSScriptRoot "apps"), (Join-Path $PSScriptRoot "core") -Recurse -Filter *.py |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ((Get-Item $exe).LastWriteTime -lt $newestSource.LastWriteTime) {
    throw "dist\ProxyChat.exe is older than $($newestSource.Name). Rebuild it first (.\build_exe.ps1); is ProxyChat.exe still running?"
}

$makensis = (Get-Command makensis -ErrorAction SilentlyContinue).Source
if (-not $makensis) {
    $candidatePaths = @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe",
        "C:\Program Files (x86)\NSIS\Bin\makensis.exe",
        "C:\Program Files\NSIS\Bin\makensis.exe"
    )
    $makensis = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $makensis) {
    throw "makensis.exe was not found. Install NSIS or add makensis to PATH."
}

& $makensis "/DAPP_VERSION=$appVersion" (Join-Path $PSScriptRoot "installer\ProxyChat.nsi")
if ($LASTEXITCODE -ne 0) {
    throw "NSIS build failed with exit code $LASTEXITCODE."
}

$setup = Join-Path $PSScriptRoot "dist\ProxyChat-Setup.exe"
$sizeMb = [math]::Round((Get-Item $setup).Length / 1MB, 1)

Write-Host ""
Write-Host "Installer complete: dist\ProxyChat-Setup.exe ($sizeMb MB, v$appVersion)"
