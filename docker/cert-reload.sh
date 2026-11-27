#!/bin/sh
# Runs from the nginx image's /docker-entrypoint.d before nginx starts.
# nginx only reads certificates at startup/reload, so poll the mounted cert
# dir and reload whenever the files change — whatever renews them on the host
# (porkbun script, certbot, ...) doesn't need to know about this container.
set -eu

interval="${CERT_RELOAD_INTERVAL:-3600}"
files="/certs/$CERT_FULLCHAIN_FILE /certs/$CERT_KEY_FILE"

fingerprint() {
    # shellcheck disable=SC2086
    cat $files 2>/dev/null | sha256sum
}

(
    last="$(fingerprint)"
    while sleep "$interval"; do
        current="$(fingerprint)"
        [ "$current" = "$last" ] && continue
        if nginx -t -q; then
            nginx -s reload
            echo "cert-reload: certificate changed, nginx reloaded"
            last="$current"
        else
            echo "cert-reload: certificate changed but nginx -t failed, keeping the running config" >&2
        fi
    done
) &
