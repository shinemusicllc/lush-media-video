#!/usr/bin/env bash
set -Eeuo pipefail

readonly -a ALLOWED_PORTS=(18188 18288)
readonly STATE_DIR="${WATCHDOG_STATE_DIR:-/run/lush-media-reverse-tunnel-watchdog}"
readonly GATEWAY="${WATCHDOG_GATEWAY:-172.19.0.1}"
readonly FAILURE_THRESHOLD="${WATCHDOG_FAILURE_THRESHOLD:-2}"
readonly CURL_BIN="${WATCHDOG_CURL_BIN:-curl}"
readonly SS_BIN="${WATCHDOG_SS_BIN:-ss}"
readonly PS_BIN="${WATCHDOG_PS_BIN:-ps}"
readonly KILL_BIN="${WATCHDOG_KILL_BIN:-kill}"
readonly LOGGER_BIN="${WATCHDOG_LOGGER_BIN:-logger}"
readonly FLOCK_BIN="${WATCHDOG_FLOCK_BIN:-flock}"

log_message() {
    "${LOGGER_BIN}" -t lush-media-reverse-tunnel-watchdog -- "$*" || true
}

is_allowed_port() {
    local requested_port="$1"
    local allowed_port
    for allowed_port in "${ALLOWED_PORTS[@]}"; do
        if [[ "${requested_port}" == "${allowed_port}" ]]; then
            return 0
        fi
    done
    return 1
}

probe_port() {
    local port="$1"
    "${CURL_BIN}" --fail --silent --show-error --max-time 8 \
        "http://${GATEWAY}:${port}/system_stats" >/dev/null 2>&1
}

failure_file() {
    printf '%s/%s.failures' "${STATE_DIR}" "$1"
}

read_failures() {
    local file="$1"
    local count=0
    if [[ -f "${file}" ]]; then
        IFS= read -r count < "${file}" || true
    fi
    if [[ ! "${count}" =~ ^[0-9]+$ ]]; then
        count=0
    fi
    printf '%s\n' "${count}"
}

listener_pid() {
    local port="$1"
    local output
    local -a pids=()
    output="$("${SS_BIN}" -H -lntp "sport = :${port}" 2>/dev/null || true)"
    while IFS= read -r pid; do
        [[ -n "${pid}" ]] && pids+=("${pid}")
    done < <(printf '%s\n' "${output}" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)

    if [[ "${#pids[@]}" -ne 1 ]]; then
        return 1
    fi
    printf '%s\n' "${pids[0]}"
}

has_active_forward_connections() {
    local port="$1"
    local output
    output="$(
        "${SS_BIN}" -H -nt state established "sport = :${port}" 2>/dev/null || true
    )"
    [[ -n "${output}" ]]
}

is_verified_deploy_sshd() {
    local pid="$1"
    local process_user process_command process_args
    process_user="$("${PS_BIN}" -o user= -p "${pid}" 2>/dev/null | tr -d '[:space:]')"
    process_command="$("${PS_BIN}" -o comm= -p "${pid}" 2>/dev/null | tr -d '[:space:]')"
    process_args="$("${PS_BIN}" -o args= -p "${pid}" 2>/dev/null | sed 's/^[[:space:]]*//')"

    [[ "${process_user}" == "deploy" ]] &&
        [[ "${process_command}" == "sshd" ]] &&
        [[ "${process_args}" == "sshd: deploy"* ]]
}

watch_port() {
    local port="$1"
    local state_file failures pid rechecked_pid
    state_file="$(failure_file "${port}")"

    if probe_port "${port}"; then
        if [[ -f "${state_file}" ]]; then
            rm -f -- "${state_file}"
            log_message "port=${port} recovered; cleared failure state"
        fi
        return 0
    fi

    failures="$(( $(read_failures "${state_file}") + 1 ))"
    printf '%s\n' "${failures}" > "${state_file}"
    log_message "port=${port} health check failed (${failures}/${FAILURE_THRESHOLD})"
    if (( failures < FAILURE_THRESHOLD )); then
        return 0
    fi

    if probe_port "${port}"; then
        rm -f -- "${state_file}"
        log_message "port=${port} recovered during recheck; no action"
        return 0
    fi

    # A large upload shares the same SSH connection as the health probe. On a
    # congested route the probe can time out while the upload is still moving.
    # Killing that listener would reset the multipart request in ComfyUI.
    if has_active_forward_connections "${port}"; then
        log_message "port=${port} has active forwarded connections; deferred stale cleanup"
        return 0
    fi

    pid="$(listener_pid "${port}" || true)"
    if [[ -z "${pid}" ]]; then
        rm -f -- "${state_file}"
        log_message "port=${port} unhealthy but has no unique SSH listener; no action"
        return 0
    fi

    rechecked_pid="$(listener_pid "${port}" || true)"
    if [[ "${pid}" != "${rechecked_pid}" ]]; then
        log_message "port=${port} listener changed during verification; no action"
        return 0
    fi

    if ! is_verified_deploy_sshd "${pid}"; then
        log_message "port=${port} pid=${pid} is not a verified deploy sshd listener; no action"
        return 0
    fi

    "${KILL_BIN}" -TERM "${pid}"
    rm -f -- "${state_file}"
    log_message "port=${port} sent TERM to verified stale deploy sshd pid=${pid}"
}

main() {
    local -a ports=("${ALLOWED_PORTS[@]}")
    if [[ "${#}" -gt 0 ]]; then
        if [[ "${#}" -ne 2 || "${1}" != "--port" || ! "${2}" =~ ^[0-9]+$ ]]; then
            echo "Usage: $0 [--port 18188|18288]" >&2
            return 64
        fi
        if ! is_allowed_port "${2}"; then
            echo "Refusing unmanaged reverse port: ${2}" >&2
            return 64
        fi
        ports=("${2}")
    fi

    mkdir -p "${STATE_DIR}"
    exec 9>"${STATE_DIR}/watchdog.lock"
    "${FLOCK_BIN}" -n 9 || return 0

    local port
    for port in "${ports[@]}"; do
        watch_port "${port}"
    done
}

main "$@"
