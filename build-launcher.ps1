$ErrorActionPreference = 'Stop'
$launcherCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $launcherCompiler)) { throw '需要 Windows .NET Framework 4 编译器。' }
$launcherOutput = Join-Path $PSScriptRoot 'plasticityassettool.exe'
& $launcherCompiler /nologo /target:winexe /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll "/out:$launcherOutput" "/win32manifest:$(Join-Path $PSScriptRoot 'launcher/Launcher.manifest.xml')" "/win32icon:$(Join-Path $PSScriptRoot 'plasticity-asset-tool-app/src/assets/favicon.ico')" (Join-Path $PSScriptRoot 'launcher/Launcher.cs')
if ($LASTEXITCODE -ne 0) { throw '启动入口构建失败。' }
Write-Output $launcherOutput
