#!/bin/sh
set -eu

log() {
    printf '%s\n' "[entrypoint] $*"
}

can_resolve_youtube() {
    getent hosts www.youtube.com >/dev/null 2>&1
}

if [ "${FIX_RESOLV_CONF:-1}" = "1" ] && ! can_resolve_youtube; then
    DNS_SERVER_1="${DNS_SERVER_1:-8.8.8.8}"
    DNS_SERVER_2="${DNS_SERVER_2:-1.1.1.1}"
    DNS_SERVER_3="${DNS_SERVER_3:-9.9.9.9}"

    log "www.youtube.com is not resolvable; rewriting /etc/resolv.conf"
    {
        printf 'nameserver %s\n' "$DNS_SERVER_1"
        printf 'nameserver %s\n' "$DNS_SERVER_2"
        printf 'nameserver %s\n' "$DNS_SERVER_3"
        printf 'options timeout:2 attempts:2 rotate single-request-reopen\n'
    } > /tmp/resolv.conf.codex

    if cp /tmp/resolv.conf.codex /etc/resolv.conf 2>/dev/null; then
        if can_resolve_youtube; then
            log "DNS recovery succeeded for www.youtube.com"
        else
            log "DNS recovery did not resolve www.youtube.com; service will return youtube_unreachable instead of HTTP 500"
        fi
    else
        log "could not rewrite /etc/resolv.conf; service will continue with existing resolver"
    fi
fi

exec "$@"
