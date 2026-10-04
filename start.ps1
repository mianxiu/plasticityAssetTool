param([switch]$Headless, [switch]$NoBuild, [switch]$Console, [switch]$NoTray, [int]$Port = 15150)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath $PSScriptRoot

if (-not $NoBuild) {
    Push-Location -LiteralPath (Join-Path $PSScriptRoot 'plasticity-asset-tool-app')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}

$assetPython = $null
$assetCandidates = @(
    (Join-Path $PSScriptRoot 'Scripts/python.exe'),
    (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
)
$assetPythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($assetPythonCommand) { $assetCandidates += $assetPythonCommand.Source }
foreach ($assetCandidate in $assetCandidates) {
    if (Test-Path -LiteralPath $assetCandidate) {
        & $assetCandidate -c 'import sys; assert sys.version_info >= (3, 10)' 2>$null
        if ($LASTEXITCODE -eq 0) { $assetPython = $assetCandidate; break }
    }
}
if (-not $assetPython) { throw 'Python 3.10+ is required. Install Python and run: python -m pip install -r requirements.txt' }

# This repository includes an older venv. Its pure-Python Tornado installation
# can also be used with a newer Python when the original venv interpreter is gone.
$assetSitePackages = Join-Path $PSScriptRoot 'Lib/site-packages'
if (Test-Path -LiteralPath (Join-Path $assetSitePackages 'tornado')) {
    $env:PYTHONPATH = "$assetSitePackages;$env:PYTHONPATH"
}
& $assetPython -c 'import tornado' 2>$null
if ($LASTEXITCODE -ne 0) { throw "Tornado is missing. Run: `"$assetPython`" -m pip install -r requirements.txt" }
$assetArguments = @('main.py', '--port', "$Port")
if ($Headless) { $assetArguments += '--headless' }
if ($NoTray) { $assetArguments += '--no-tray' }
$assetWindowlessPython = Join-Path (Split-Path $assetPython) 'pythonw.exe'
if (-not $Console -and -not $NoTray -and (Test-Path -LiteralPath $assetWindowlessPython)) {
    $assetArguments[0] = '"' + (Join-Path $PSScriptRoot 'main.py') + '"'
    Start-Process -FilePath $assetWindowlessPython -ArgumentList $assetArguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden | Out-Null
    Write-Output 'Plasticity 组件库已启动：通过系统托盘图标查看连接、打开组件库或退出服务。'
} else {
    & $assetPython @assetArguments
}
