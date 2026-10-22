param(
    # libopus'suz derlemek bilincli bir tercih olmali: o exe'de ses mu-law'a
    # duser (cerceve 320 bayt, Opus'ta 60) ve odaya Opus'lu biri once girerse
    # bu kopya sese hic giremez. Sessizce olmasin diye anahtar isteniyor.
    [switch]$Opussuz
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Derleme ayarlarinin tek kaynagi ProxyChat.spec dosyasidir; buradaki betik
# yalnizca dogru Python'u, pyinstaller'in varligini ve libopus'un yerini
# garanti eder.

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Sanal ortam bulunamadi, sistem Python'u kullanilacak."
    $python = "python"
}

# libopus depoda durmuyor (gerekcesi THIRD-PARTY.md icinde): derleme aninda
# disaridan gosteriliyor ve spec onu pakete gomuyor.
$opus = $env:PROXYCHAT_OPUS_DLL
if ($Opussuz) {
    $env:PROXYCHAT_OPUS_DLL = ""
    Write-Host "libopus BILEREK disarida birakildi; bu exe'de ses mu-law olacak."
} elseif (-not $opus) {
    throw @"
PROXYCHAT_OPUS_DLL ayarli degil, yani exe libopus'suz cikardi ve ses mu-law'a
duserdi. Bu sessizce olmamali.

  DLL'i gosterip yeniden dene:
    `$env:PROXYCHAT_OPUS_DLL = "$PSScriptRoot\dist\libopus.dll"

  Ya da bilerek Opus'suz derle:
    .\build_exe.ps1 -Opussuz
"@
} elseif (-not (Test-Path $opus)) {
    throw "PROXYCHAT_OPUS_DLL gosterdigi dosya yok: $opus"
} else {
    $ozet = (Get-FileHash $opus -Algorithm SHA256).Hash.ToLower()
    Write-Host "libopus paketlenecek: $opus"
    Write-Host "  SHA-256: $ozet"
    Write-Host "  (bu ozet THIRD-PARTY.md icindekiyle ayni olmali)"
}

# --- Yeniden uretilebilirlik (THREAT_MODEL 5.9, 8-A) --------------------
# Olculdu (2026-09-29): bu iki degisken olmadan ayni kaynaktan yapilan uc
# derleme uc farkli ozet veriyordu. Farkin buyuk kismi tek bir kok nedenin
# golgesi: zlib, arsivin basindaki kucuk bir farki sonuna kadar yayiyor.
#
# SOURCE_DATE_EPOCH git commit zamanindan turetiliyor, yani depoyu klonlayan
# herkes ayni degeri uretebiliyor -- "benim makinemde" olmayan bir sayi.
# Kaynak dosyalarin mtime'ini ellemeye gerek yok, bu tek basina yetiyor
# (test edildi). PYTHONHASHSEED sirasi etkileyen sozluk/kume duzenini
# sabitliyor; gerekliligi izole edilmedi, bedeli sifir oldugu icin duruyor.
#
# Ortamda zaten bir SOURCE_DATE_EPOCH varsa ona dokunulmuyor. Yayin deposu
# gelistirme deposunun bir kopyasi; oradaki son commit'in zamani farkli,
# yani o depodan derleyen biri imzali exe'yi ancak yayinlanan derleme
# kunyesindeki degeri vererek yeniden uretebilir (VERIFYING.md).
#
# git cagrilari bu yardimcidan geciyor: Windows PowerShell 5.1'de, yukaridaki
# "Stop" ayari acikken git'in stderr'e yazdigi tek satir ("not a git
# repository") olumcul hataya donusuyor ve derleme cokuyordu. Kaynagi ZIP
# olarak indiren biri tam bu durumda. Basarisiz git cagrisi $null doner.
function Invoke-GitSessiz {
    $onceki = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $cikti = & git @args 2>$null
        if ($LASTEXITCODE -eq 0) { return $cikti }
    } catch {
    } finally {
        $ErrorActionPreference = $onceki
    }
    return $null
}

$commitZamani = Invoke-GitSessiz log -1 --format=%ct
if ($env:SOURCE_DATE_EPOCH -match '^\d+$') {
    $okunur = [DateTimeOffset]::FromUnixTimeSeconds([int64]$env:SOURCE_DATE_EPOCH).UtcDateTime
    Write-Host "SOURCE_DATE_EPOCH = $env:SOURCE_DATE_EPOCH  ($okunur UTC, ortamdan verildi)"
} elseif ($env:SOURCE_DATE_EPOCH) {
    throw "SOURCE_DATE_EPOCH bir tam sayi olmali (unix zamani), verilen: '$env:SOURCE_DATE_EPOCH'"
} elseif ($commitZamani) {
    $env:SOURCE_DATE_EPOCH = $commitZamani.Trim()
    $okunur = [DateTimeOffset]::FromUnixTimeSeconds([int64]$env:SOURCE_DATE_EPOCH).UtcDateTime
    Write-Host "SOURCE_DATE_EPOCH = $env:SOURCE_DATE_EPOCH  ($okunur UTC, son commit)"
} else {
    Write-Host "UYARI: git yok ya da depo degil; SOURCE_DATE_EPOCH ayarlanmadi."
    Write-Host "       Bu derleme bit bit yeniden uretilebilir OLMAYACAK."
}
$env:PYTHONHASHSEED = "0"

# Calisma agaci kirliyse uretilen exe hicbir commit'e karsilik gelmiyor
# demektir; ozeti yayinlamak yanlis olur. Durdurmuyoruz, cunku gelistirirken
# surekli boyle deniyor -- ama soyluyoruz.
$kirli = Invoke-GitSessiz status --porcelain
if ($kirli) {
    Write-Host "UYARI: calisma agaci temiz degil. Bu exe bir commit'e karsilik"
    Write-Host "       gelmiyor; ozetini yayinlamadan once commit et."
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
}

& $python -m PyInstaller --noconfirm --clean ProxyChat.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

$exe = Join-Path $PSScriptRoot "dist\ProxyChat.exe"
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)

Write-Host ""
Write-Host "Build complete: dist\ProxyChat.exe ($sizeMb MB)"
if (-not $Opussuz) {
    Write-Host "libopus pakete gomuldu; DLL'i exe'nin yanina koymaya gerek yok."
}
