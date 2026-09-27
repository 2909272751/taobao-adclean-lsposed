#!/system/bin/sh
for p in com.taobao.taobao com.taobao.idlefish; do
  echo "=== $p all verified-splits ($(ls /data/data/$p/files/splitcompat/*/verified-splits/*.apk 2>/dev/null | wc -l)) ==="
  ls -l /data/data/$p/files/splitcompat/*/verified-splits/*.apk 2>/dev/null | awk '{printf "%9d %s\n", $5, $NF}' | sort -k2
done
echo "=== idlefish dexpatch / other dex ==="
ls -l /data/data/com.taobao.idlefish/dexpatch 2>/dev/null | head -20
find /data/data/com.taobao.idlefish -maxdepth 4 -name '*.dex' -o -maxdepth 4 -name '*.jar' -o -maxdepth 4 -name '*.apk' 2>/dev/null | head -40
