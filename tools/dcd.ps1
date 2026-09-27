# Parallel batch single-class decompiler (jadx 1.5.5).
# Usage: pwsh -NoProfile -File tools\dcd.ps1 -List <file-with-class-names> [-Par 6]
param(
  [Parameter(Mandatory=$true)][string]$List,
  [int]$Par = 6
)
$root = 'C:\实用软件开发\taobao-adclean-lsposed'
$apk  = Join-Path $root 'reference-apk\taobao-10.66.30-base.apk'
$out  = Join-Path $root 'scratch-recon\jadx-tb'
$logs = Join-Path $root 'scratch-recon\logs'
New-Item -ItemType Directory -Force -Path $out, $logs | Out-Null

$classes = Get-Content -LiteralPath $List | Where-Object { $_.Trim() -ne '' -and -not $_.Trim().StartsWith('#') } | ForEach-Object { $_.Trim() }
if ($classes.Count -eq 0) { Write-Output 'empty list'; exit 1 }

# skip classes already decompiled and non-empty
$todo = @()
foreach ($c in $classes) {
  $leaf = ($c -split '\.')[-1]
  $f = Join-Path $out "$leaf.java"
  if ((Test-Path -LiteralPath $f) -and ((Get-Item -LiteralPath $f).Length -gt 200)) { continue }
  $todo += $c
}
Write-Output "total=$($classes.Count) todo=$($todo.Count) par=$Par"

$chunks = @{}
for ($i = 0; $i -lt $Par; $i++) { $chunks[$i] = New-Object System.Collections.ArrayList }
$k = 0
foreach ($c in $todo) { [void]$chunks[$k % $Par].Add($c); $k++ }

$procs = @()
for ($i = 0; $i -lt $Par; $i++) {
  if ($chunks[$i].Count -eq 0) { continue }
  $cf = Join-Path $logs "_chunk$i.txt"
  Set-Content -LiteralPath $cf -Value ($chunks[$i] -join "`n") -Encoding UTF8
  $p = Start-Process -FilePath 'powershell.exe' -PassThru -WindowStyle Hidden `
       -ArgumentList @('-NoProfile','-File', (Join-Path $root 'tools\dcd-one.ps1'), $cf, "$i") `
       -RedirectStandardOutput (Join-Path $logs "_chunk$i.log") `
       -RedirectStandardError  (Join-Path $logs "_chunk$i.err")
  $procs += $p
}
foreach ($p in $procs) { $p.WaitForExit() }
Write-Output "done; produced:"
Get-ChildItem -LiteralPath $out -Filter *.java | Sort-Object Name | ForEach-Object { "  $($_.Name)  $($_.Length)" }
