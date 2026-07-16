#!/usr/bin/env bash
#
# sign-prepare-fota.sh - compute MCUboot FOTA digests from the B0-signed MCUboot
# images and write them as Vault signing requests into manifest-fota-tosign.env.
# Runs in CI after sign-assemble.sh has produced the B0-signed MCUboot images.
#
# Only needed for MCUboot FOTA releases. App-only releases do not require this
# step; the single sign-prepare / sign-hashes / sign-assemble trip is sufficient.
#
# The secure environment then signs the requests with Vault (sign-hashes.sh),
# and sign-assemble-fota.sh applies the returned signatures to produce the
# dual-signed signed_by_mcuboot_and_b0_mcuboot images.
#
# Options:
#   --release-dir DIR   Dir with B0-signed MCUboot images. Default: ${RELEASE_DIR}
#   --output FILE       Output manifest. Default: ${OUT_DIR}/manifest-fota-tosign.env

set -euo pipefail
SCRIPT_NAME="sign-prepare-fota"
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

TOSIGN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --release-dir) RELEASE_DIR="${2:?}"; shift 2 ;;
        --output)      TOSIGN="${2:?}"; shift 2 ;;
        -h|--help)     sed -n '2,18p' "$0"; exit 0 ;;
        *)             err "unknown argument: $1 (see --help)" ;;
    esac
done
TOSIGN="${TOSIGN:-${OUT_DIR}/manifest-fota-tosign.env}"

# --- Preconditions -----------------------------------------------------------

require_python_imgtool
APP_PUB="$(mcuboot_pub_pem)"
require_file "${APP_PUB}" "committed MCUboot public key (certificates/)"

B0_S0="${RELEASE_DIR}/signed_by_b0_mcuboot.bin"
B0_S1="${RELEASE_DIR}/signed_by_b0_mcuboot_s1_variant.bin"
require_file "${B0_S0}" "B0-signed MCUboot S0 (run sign-assemble.sh first)"
require_file "${B0_S1}" "B0-signed MCUboot S1 variant (run sign-assemble.sh first)"

MANIFEST="${RELEASE_DIR}/${MANIFEST_FILE_NAME}"
require_file "${MANIFEST}" "release manifest (run sign-assemble.sh first)"
# shellcheck disable=SC1090
. "${MANIFEST}"
: "${PROV_S0_ADDR:?manifest missing PROV_S0_ADDR}"
: "${PROV_S1_ADDR:?manifest missing PROV_S1_ADDR}"
: "${MCUBOOT_VERSION:?manifest missing MCUBOOT_VERSION}"
: "${MCUBOOT_SLOT_SIZE:?manifest missing MCUBOOT_SLOT_SIZE}"
: "${MCUBOOT_HEADER_SIZE:?manifest missing MCUBOOT_HEADER_SIZE}"
: "${MCUBOOT_ALIGN:?manifest missing MCUBOOT_ALIGN}"

WORK="$(mktemp -d)"; trap 'rm -rf "${WORK}"' EXIT
mkdir -p "$(dirname "${TOSIGN}")"

# Build a clean fota manifest: strip all SIGN_* lines from the release manifest
# so that neither the round-1 SIGN_ITEMS nor the round-1 signatures are carried
# through. get_field() in sign-hashes.sh returns the first match, so any
# existing SIGN_ITEMS from round 1 would shadow the fota SIGN_ITEMS we append.
grep -v '^SIGN_' "${MANIFEST}" > "${TOSIGN}"
{
    echo ""
    echo "# === MCUboot FOTA signing requests (sign-prepare-fota.sh) - sign with Vault"
} >> "${TOSIGN}"

ITEMS=()
add_fota_request() {  # <name> <rom_fixed_addr> <b0_signed_bin>
    local name="$1" rom_fixed="$2" b0_bin="$3"
    ITEMS+=("${name}")
    log "  ${name}: imgtool digest (rom-fixed=${rom_fixed})"
    mcuboot_fota_digest "${rom_fixed}" "${APP_PUB}" "${b0_bin}" "${WORK}/${name}.digest"
    cat >> "${TOSIGN}" <<EOF
SIGN_${name}_KEY="${MCUBOOT_KEY_NAME}"
SIGN_${name}_PREHASHED="true"
SIGN_${name}_HASH_ALGORITHM="sha2-256"
SIGN_${name}_MARSHALING="asn1"
SIGN_${name}_INPUT_B64="$(base64 < "${WORK}/${name}.digest" | tr -d '\n')"
EOF
}

log "Computing MCUboot FOTA digests (imgtool) for MCUBOOT to sign"
add_fota_request mcuboot_fota_s0 "${PROV_S0_ADDR}" "${B0_S0}"
add_fota_request mcuboot_fota_s1 "${PROV_S1_ADDR}" "${B0_S1}"

echo "SIGN_ITEMS=\"${ITEMS[*]}\"" >> "${TOSIGN}"

ok "Prepared ${#ITEMS[@]} MCUboot FOTA signing request(s) -> ${TOSIGN}"
log "Requests: ${ITEMS[*]}"
log "Next (in the secure env): ./sign-hashes.sh --in manifest-fota-tosign.env --out manifest-fota-signed.env"
