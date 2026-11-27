#!/bin/sh
# Runs from the nginx image's /docker-entrypoint.d after the config template is
# rendered. On the host's network nginx can only bind [::] when the host has
# IPv6, so on a host without it keep just the IPv4 listen line.
set -eu

conf=/etc/nginx/conf.d/default.conf
if [ ! -e /proc/net/if_inet6 ]; then
    grep -v 'listen \[::\]:' "$conf" > "$conf.tmp"
    mv "$conf.tmp" "$conf"
    echo "ipv6-listen: host has no IPv6, listening on IPv4 only"
fi
