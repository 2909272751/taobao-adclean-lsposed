#!/system/bin/sh
for p in com.taobao.taobao com.taobao.idlefish; do
  echo "=== $p dex/jar/apk under /data/data ==="
  find /data/data/$p -maxdepth 5 \( -name '*.dex' -o -name '*.jar' -o -name '*.apk' -o -name '*.zip' \) 2>/dev/null | head -40
  echo "=== $p bundle-ish dirs ==="
  ls -d /data/data/$p/files/* 2>/dev/null | head -60
done
echo "=== taobao external ==="
find /sdcard/Android/data/com.taobao.taobao -maxdepth 4 -type d 2>/dev/null | head -30
find /sdcard/Android/data/com.taobao.idlefish -maxdepth 4 -type d 2>/dev/null | head -30
