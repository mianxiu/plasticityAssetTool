param(
    [string]$Target,
    [string]$Backup,
    [string]$UpgradeFrom,
    [string]$BaseBackup,
    [string]$Description = '安装或更新内嵌组件库插件，支持组件保存、置入和默认布尔模式',
    [string]$Python,
    [switch]$Restore,
    [switch]$BuildOnly,
    [switch]$Preview
)
$ErrorActionPreference = 'Stop'
$installerRoot = $PSScriptRoot
$installerRuntime = Join-Path $installerRoot '.runtime'
New-Item -ItemType Directory -Path $installerRuntime -Force | Out-Null
$installerExe = Join-Path $installerRuntime 'PlasticityAssetTool.PluginInstaller.exe'
$installerCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $installerCompiler)) { throw '需要 Windows .NET Framework 4 编译器。' }
& $installerCompiler /nologo /target:winexe /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "/out:$installerExe" "/win32manifest:$(Join-Path $installerRoot 'installer/PluginInstaller.manifest.xml')" "/win32icon:$(Join-Path $installerRoot 'plasticity-asset-tool-app/src/assets/favicon.ico')" (Join-Path $installerRoot 'installer/PluginInstaller.cs')
if ($LASTEXITCODE -ne 0) { throw '安装器构建失败。' }
if ($BuildOnly) { Write-Output $installerExe; return }
if (-not $Backup) { throw '请指定 -Backup 回滚备份路径。' }
if (-not $Restore -and -not $Target) { throw '请指定 -Target Plasticity 的 .webpack/main/index.js。' }
if ($Restore) {
    $restoreManifest = Get-Content -LiteralPath ([IO.Path]::ChangeExtension($Backup, '.manifest.json')) -Raw | ConvertFrom-Json
    $Target = $restoreManifest.target
    $Description = '恢复原插件入口：' + $Description
}
if (-not $Python) {
    $Python = Join-Path $installerRoot 'runtime/python/python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { $Python = Join-Path $installerRoot '.venv/Scripts/python.exe' }
    if (-not (Test-Path -LiteralPath $Python)) { $Python = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' }
    if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python.exe -ErrorAction Stop).Source }
}
$installerArgs = @('--backup', [IO.Path]::GetFullPath($Backup))
if ($Restore) { $installerArgs += '--restore' }
else {
    $installerArgs += @('--target', [IO.Path]::GetFullPath($Target))
    if ($UpgradeFrom) { $installerArgs += @('--upgrade-from', [IO.Path]::GetFullPath($UpgradeFrom)) }
    if ($BaseBackup) { $installerArgs += @('--base-backup', [IO.Path]::GetFullPath($BaseBackup)) }
}
$installerRequest = Join-Path $installerRuntime ('plugin-install-' + [guid]::NewGuid().ToString('N') + '.json')
$installerResult = [IO.Path]::ChangeExtension($installerRequest, '.txt')
@{root=$installerRoot;python=[IO.Path]::GetFullPath($Python);target=[IO.Path]::GetFullPath($Target);backup=[IO.Path]::GetFullPath($Backup);description=$Description;arguments=$installerArgs;result=$installerResult} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $installerRequest -Encoding UTF8
$installerLaunchArgs = '"' + $installerRequest + '"'
if ($Preview) { $installerLaunchArgs += ' --preview-image "' + (Join-Path $installerRuntime 'plugin-installer-preview.png') + '"' }
try {
    $installerProcess = Start-Process -FilePath $installerExe -ArgumentList $installerLaunchArgs -Wait -PassThru
    if ($installerProcess.ExitCode -eq 1223) { Write-Output '安装或 Windows 权限请求已取消，未执行安装。'; exit 1223 }
    if ($installerProcess.ExitCode -ne 0) { throw "安装未完成，请查看：$installerResult" }
    if (Test-Path -LiteralPath $installerResult) { Get-Content -LiteralPath $installerResult }
} finally { Remove-Item -LiteralPath $installerRequest -ErrorAction SilentlyContinue }
