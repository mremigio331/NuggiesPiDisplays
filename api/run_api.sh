#!/bin/bash
cd "$(dirname "$0")"
# Dev only. Listen on IPv4 and IPv6 so <name>.local works when a client picks
# the IPv6 answer. --reload binds one socket itself: "::" is dual-stack only
# when the Pi has IPv6 on and bindv6only=0; otherwise stay on IPv4.
HOST=0.0.0.0
if [[ -e /proc/net/if_inet6 && "$(cat /proc/sys/net/ipv6/bindv6only 2>/dev/null)" == "0" ]]; then
    HOST=::
fi
python3 -m uvicorn main:app --host "$HOST" --port 8000 --reload
