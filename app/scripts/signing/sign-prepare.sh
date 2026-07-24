#!/usr/bin/env bash
#
# sign-prepare.sh - compute the hashes/digests that need a private key and write
# them into manifest-tosign.env, inside the unsigned bundle. Runs in CI right
# after build-unsigned.sh (needs the toolchain and the committed MCUboot public
# key; touches NO private key and does NOT contact Vault).
#
# The secure environment then signs the requests with Vault:
#     sign-hashes.sh --in manifest-tosign.env --out manifest-signed.env
# and sign-assemble.sh applies the returned signatures to build flashable images.
#
# What needs signing (everything else is public computation, in prepare/assemble):
#   nsib_s0, nsib_s1   B0 signs the hash of each MCUboot slot   (prehashed=false)
#   app                MCUBOOT signs the app image digest        (prehashed=true)
#
# Options:
#   --unsigned-dir DIR   Input bundle dir.  Default: ${UNSIGNED_DIR}
#   --output FILE        manifest-tosign.env. Default: <unsigned-dir>/manifest-tosign.env
#   --app-only           Only emit the app request (re-sign app, reuse bootloader).

set -euo pipefail
SCRIPT_NAME="sign-prepare"
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

APP_ONLY=0
MCUBOOT_KEY_VER=1
B0_KEY_VER=1
TOSIGN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --unsigned-dir)          UNSIGNED_DIR="${2:?}"; shift 2 ;;
        --output)                TOSIGN="${2:?}"; shift 2 ;;
        --app-only)              APP_ONLY=1; shift ;;
        --mcuboot-key-version)   MCUBOOT_KEY_VER="${2:?}"; shift 2 ;;
        --b0-key-version)        B0_KEY_VER="${2:?}"; shift 2 ;;
        -h|--help)               sed -n '2,30p' "$0"; exit 0 ;;
        *)                       err "unknown argument: $1 (see --help)" ;;
    esac
done
TOSIGN="${TOSIGN:-${UNSIGNED_DIR}/${TOSIGN_FILE_NAME}}"

# --- Preconditions (toolchain + committed MCUboot pubkey; no Vault) ----------

require_python_imgtool
APP_PUB="$(mcuboot_pub_pem)"
# Key rotation: use the next public key when --mcuboot-key-version 2 is given.
if [ "${MCUBOOT_KEY_VER}" = "2" ]; then
    APP_PUB="$(pub_pem "${MCUBOOT_KEY_NAME_NEXT}")"
    log "Key rotation: using ${MCUBOOT_KEY_NAME_NEXT} (${APP_PUB}) for app digest"
fi
require_file "${APP_PUB}" "committed MCUboot public key (certificates/)"
[ "${APP_ONLY}" = "0" ] && require_file "${HASH_PY}" "hash.py"

MANIFEST="${UNSIGNED_DIR}/${MANIFEST_FILE_NAME}"
require_file "${MANIFEST}" "unsigned bundle manifest (run build-unsigned.sh first)"
# shellcheck disable=SC1090
. "${MANIFEST}"

U_APP="${UNSIGNED_DIR}/app_unsigned.hex"
require_file "${U_APP}" "unsigned artifact"
if [ "${APP_ONLY}" = "0" ]; then
    U_S0="${UNSIGNED_DIR}/mcuboot_s0.hex"
    U_S1="${UNSIGNED_DIR}/mcuboot_s1.hex"
    require_file "${U_S0}" "unsigned artifact"
    require_file "${U_S1}" "unsigned artifact"
fi

WORK="$(mktemp -d)"; trap 'rm -rf "${WORK}"' EXIT
mkdir -p "$(dirname "${TOSIGN}")"

# Seed the to-sign manifest with the build parameters, then append the requests.
cp "${MANIFEST}" "${TOSIGN}"
{
    echo ""
    echo "# === signing requests (sign-prepare.sh) - sign with Vault, see sign-hashes.sh"
} >> "${TOSIGN}"

ITEMS=()
add_request() {  # <name> <key-name> <prehashed> <input-b64>
    local name="$1" key="$2" prehashed="$3" b64="$4"
    ITEMS+=("${name}")
    cat >> "${TOSIGN}" <<EOF
SIGN_${name}_KEY="${key}"
SIGN_${name}_PREHASHED="${prehashed}"
SIGN_${name}_HASH_ALGORITHM="sha2-256"
SIGN_${name}_MARSHALING="asn1"
SIGN_${name}_INPUT_B64="${b64}"
EOF
}

if [ "${APP_ONLY}" = "0" ]; then
    # B0 key rotation: use the second B0 key when --b0-key-version 2 is given.
    _b0_key_name="${NSIB_KEY_NAME}"
    if [ "${B0_KEY_VER}" = "2" ]; then
        [ -n "${NSIB_KEY_NAME_2:-}" ] || err "--b0-key-version 2 requires NSIB_KEY_NAME_2 in the manifest; build with --b0-key-name-2"
        _b0_key_name="${NSIB_KEY_NAME_2}"
        log "B0 key rotation: using ${NSIB_KEY_NAME_2} for MCUboot signing requests"
    fi
    log "Hashing MCUboot slots (hash.py) for B0 to sign"
    nsib_hash "${U_S0}" "${WORK}/s0.hash"
    nsib_hash "${U_S1}" "${WORK}/s1.hash"
    # B0 signs the hash-file contents; Vault does the SHA256 (prehashed=false).
    add_request nsib_s0 "${_b0_key_name}" false "$(base64 < "${WORK}/s0.hash" | tr -d '\n')"
    add_request nsib_s1 "${_b0_key_name}" false "$(base64 < "${WORK}/s1.hash" | tr -d '\n')"
fi

log "Computing app image digest (imgtool) for MCUBOOT to sign"
app_digest "${APP_PUB}" "${U_APP}" "${WORK}/app.digest"
# Select vault key name based on key version.
_app_key_name="${MCUBOOT_KEY_NAME}"
[ "${MCUBOOT_KEY_VER}" = "2" ] && _app_key_name="${MCUBOOT_KEY_NAME_NEXT}"
# MCUBOOT key signs the digest directly (prehashed=true).
add_request app "${_app_key_name}" true "$(base64 < "${WORK}/app.digest" | tr -d '\n')"

echo "SIGN_ITEMS=\"${ITEMS[*]}\"" >> "${TOSIGN}"

ok "Prepared ${#ITEMS[@]} signing request(s) -> ${TOSIGN}"
log "Requests: ${ITEMS[*]}"
log "Next (in the secure env): ./sign-hashes.sh --in ${TOSIGN_FILE_NAME} --out manifest-signed.env"
