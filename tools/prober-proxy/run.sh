#!/bin/bash
# Start the Diving-Fish proxy updater, then put the Wi-Fi proxy settings back the way they were.
#
# The updater points the Wi-Fi HTTP/HTTPS proxy at 127.0.0.1:8033 and, on exit, only switches them off, which would
# leave a proxy configured before (Clash and the like) disabled. This restores the saved values instead.
# Extra arguments go to the updater, e.g. ./run.sh -reauth
set -u
cd "$(dirname "$0")"
SERVICE=Wi-Fi
ARCH=$(uname -m); [ "$ARCH" = x86_64 ] && ARCH=amd64
BIN=$(ls ./maimaidx-prober-proxy-darwin-"$ARCH"-* 2>/dev/null | sort -V | tail -1)
if [ -z "$BIN" ]; then
    echo "没有找到 maimaidx-prober-proxy-darwin-$ARCH-*：先从 https://github.com/Diving-Fish/maimaidx-prober/releases 下载到这个目录" >&2
    exit 1
fi
chmod +x "$BIN"

save() { # $1 = -getwebproxy | -getsecurewebproxy
    networksetup "$1" "$SERVICE" | awk -F': ' '/^Enabled/{e=$2} /^Server/{s=$2} /^Port/{p=$2} END{print e, s, p}'
}
read -r WEB_ON WEB_HOST WEB_PORT < <(save -getwebproxy)
read -r SEC_ON SEC_HOST SEC_PORT < <(save -getsecurewebproxy)

restore() {
    if [ "$WEB_ON" = Yes ]; then
        networksetup -setwebproxy "$SERVICE" "$WEB_HOST" "$WEB_PORT"
    else
        networksetup -setwebproxystate "$SERVICE" off
    fi
    if [ "$SEC_ON" = Yes ]; then
        networksetup -setsecurewebproxy "$SERVICE" "$SEC_HOST" "$SEC_PORT"
    else
        networksetup -setsecurewebproxystate "$SERVICE" off
    fi
    echo "Wi-Fi 代理已恢复: HTTP $WEB_ON $WEB_HOST:$WEB_PORT, HTTPS $SEC_ON $SEC_HOST:$SEC_PORT"
}
trap restore EXIT

"$BIN" "$@"
