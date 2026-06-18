#!/usr/bin/env bash
#
# Shared configuration and helpers for build-unsigned.sh. Sourced, not run.
# Override any variable below by exporting it before calling the script.

# --- Paths -------------------------------------------------------------------

SIGN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "${SIGN_DIR}/../.." && pwd)}"
NCS_DIR="${NCS_DIR:-$(cd "${APP_DIR}/../.." && pwd)}"

BOARD="${BOARD:-nrf9151dk/nrf9151/ns}"

BUILD_DIR="${BUILD_DIR:-${APP_DIR}/build}"
KEYS_DIR="${KEYS_DIR:-${APP_DIR}/signing-keys}"      # public verification key(s)
OUT_DIR="${OUT_DIR:-${APP_DIR}/signing-out}"
UNSIGNED_DIR="${UNSIGNED_DIR:-${OUT_DIR}/unsigned}"  # build-unsigned.sh output bundle
MANIFEST_FILE_NAME="manifest.env"                    # signing parameters captured at build time

# --- Signing parameters (captured into the manifest) -------------------------

SLOT_SIZE="${SLOT_SIZE:-0x6f000}"
HEADER_SIZE="${HEADER_SIZE:-0x200}"
ALIGN="${ALIGN:-4}"
APP_VERSION_DEFAULT="${APP_VERSION_DEFAULT:-1.99.0+0}"
MCUBOOT_VERSION_DEFAULT="${MCUBOOT_VERSION_DEFAULT:-0.0.0+0}"

# --- MCUboot application verification key ------------------------------------

MCUBOOT_KEY_NAME="${MCUBOOT_KEY_NAME:-mcuboot}"
mcuboot_pub_pem() { echo "${KEYS_DIR}/${MCUBOOT_KEY_NAME}_pub.pem"; }

# --- Output formatting -------------------------------------------------------

_c_red='\033[31m'; _c_grn='\033[32m'; _c_yel='\033[33m'; _c_cya='\033[36m'; _c_rst='\033[0m'
log()  { printf "${_c_cya}[%s]${_c_rst} %s\n" "${SCRIPT_NAME:-signing}" "$*" >&2; }
ok()   { printf "${_c_grn}[%s] %s${_c_rst}\n" "${SCRIPT_NAME:-signing}" "$*" >&2; }
warn() { printf "${_c_yel}[%s] warning:${_c_rst} %s\n" "${SCRIPT_NAME:-signing}" "$*" >&2; }
err()  { printf "${_c_red}[%s] error:${_c_rst} %s\n" "${SCRIPT_NAME:-signing}" "$*" >&2; exit 1; }

# --- Precondition checks -----------------------------------------------------

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || err "required command '$1' not found in PATH. $2"
}

require_file() {
    [ -f "$1" ] || err "${2:-required file} not found: $1"
}
