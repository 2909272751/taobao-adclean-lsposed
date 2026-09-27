param(
  [Parameter(Mandatory=$true)][string]$Package,
  [string]$Tag = 'probe',
  [int[]]$Shots = @(3, 7, 12, 20)
)
# Launch a target app, capture screenshots at absolute second offsets, then dump the UI tree.
# Usage: powershell -File tools\ui_probe.ps1 -Package com.taobao.idlefish -Tag home
$adb = 'C:\Android\adb.exe'
$out = Join-Path (Split-Path $PSScriptRoot -Parent) 'scratch-recon\ui'
New-Item -ItemType Directory -Force $out | Out-Null

& $adb shell am force-stop $Package
Start-Sleep -Milliseconds 800
& $adb logcat -c
& $adb shell monkey -p $Package -c android.intent.category.LAUNCHER 1 | Out-Null

$elapsed = 0
foreach ($t in ($Shots | Sort-Object)) {
  $delta = $t - $elapsed
  if ($delta -gt 0) { Start-Sleep -Seconds $delta }
  $elapsed = $t
  & $adb shell screencap -p /sdcard/p.png
  $local = Join-Path $out ("{0}-t{1}.png" -f $Tag, $t)
  & $adb pull /sdcard/p.png $local 2>$null | Out-Null
  $len = (Get-Item $local -ErrorAction SilentlyContinue).Length
  Write-Host ("shot t={0}s -> {1} ({2} bytes)" -f $t, $local, $len)
}
& $adb shell rm -f /sdcard/p.png

# uiautomator waits for UI idle and can block forever on an animating feed;
# toybox timeout keeps the probe bounded.
& $adb shell "timeout 20 uiautomator dump /sdcard/ui.xml" | Out-Null
$ui = Join-Path $out ("{0}-ui.xml" -f $Tag)
& $adb pull /sdcard/ui.xml $ui 2>$null | Out-Null
& $adb shell rm -f /sdcard/ui.xml
Write-Host ("ui -> {0}" -f $ui)
