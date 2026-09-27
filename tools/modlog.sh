#!/system/bin/sh
# Dump this module's log lines from the newest LSPosed per-module log.
# Usage: sh /data/local/tmp/modlog.sh [arm|hits|all]
#   arm  = rule armed / rule unavailable / feature= / install_summary
#   hits = blocked id= / hid id/   (闸门真的被调用到的证据)
#   all  = everything for this module, main process only
MODE=${1:-hits}
LOG=$(ls -t /data/adb/lspd/log/modules_*.log | head -1)
case "$MODE" in
  arm)  grep -h -e 'rule armed' -e 'rule unavailable' -e 'feature=' -e 'install_summary' "$LOG" | tail -n 80 ;;
  hits) grep -h -e 'blocked id=' -e 'hid id/' "$LOG" | tail -n 80 ;;
  *)    grep -h 'io.github.taobaoadclean' "$LOG" | grep -v ':channel' | grep -v 'gpu_process' | grep -v 'normal_render' | tail -n 80 ;;
esac
