param([string]$ChunkFile, [string]$Tag = '0')
$root = 'C:\实用软件开发\taobao-adclean-lsposed'
$apk  = Join-Path $root 'reference-apk\taobao-10.66.30-base.apk'
$out  = Join-Path $root 'scratch-recon\jadx-tb'
$jadx = 'C:\实用软件开发\tools\jadx-1.5.5\bin\jadx.bat'
$classes = Get-Content -LiteralPath $ChunkFile | Where-Object { $_.Trim() -ne '' }
foreach ($c in $classes) {
  $leaf = ($c -split '\.')[-1]
  $target = Join-Path $out "$leaf.java"
  & $jadx -r --no-imports --single-class $c --single-class-output $target $apk *> (Join-Path $root "scratch-recon\logs\one-$Tag-$leaf.log")
}
