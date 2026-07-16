#!/usr/bin/env bash
#
# sign-assemble-fota.sh - apply Vault MCUBOOT signatures to the B0-signed MCUboot
# images to produce the dual-signed signed_by_mcuboot_and_b0_mcuboot images
# needed for MCUboot FOTA updates. Runs in CI after the second sign-hashes.sh trip.
#
# This is the second assemble step; it is ONLY needed for MCUboot FOTA releases.
# App-only releases use sign-assemble.sh alone (single secure-env trip).
#
# Inputs (from ${RELEASE_DIR} unless overridden):
#   signed_by_b0_mcuboot.bin/.hex            produced by sign-assemble.sh
#   signed_by_b0_mcuboot_s1_variant.bin/.hex produced by sign-assemble.sh
#   manifest.env                             produced by sign-assemble.sh
#   manifest-fota-signed.env                 produced by sign-hashes.sh (second trip)
#
# Emits (under ${RELEASE_DIR}):
#   signed_by_mcuboot_and_b0_mcuboot.hex/.bin
#   signed_by_mcuboot_and_b0_mcuboot_s1_variant.hex/.bin
#
# Options:
#   --fota-signed FILE    manifest-fota-signed.env.  Default: ${OUT_DIR}/manifest-fota-signed.env
#   --release-dir DIR     Input/output directory.    Default: ${RELEASE_DIR}

set -euo pipefail
SCRIPT_NAME="sign-assemble-fota"
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

FOTA_SIGNED="${OUT_DIR}/manifest-fota-signed.env"
while [ $# -gt 0 ]; do
    case "$1" in
        --fota-signed) FOTA_SIGNED="${2:?}"; shift 2 ;;
        --release-dir) RELEASE_DIR="${2:?}"; shift 2 ;;
        -h|--help)     sed -n '2,24p' "$0"; exit 0 ;;
        *)             err "unknown argument: $1 (see --help)" ;;
    esac
done

# --- Preconditions -----------------------------------------------------------

require_python_imgtool
require_file "${FOTA_SIGNED}" "MCUboot FOTA signed manifest (run sign-hashes.sh second trip)"
APP_PUB="$(mcuboot_pub_pem)"
require_file "${APP_PUB}" "committed MCUboot public key (certificates/)"

B0_S0_BIN="${RELEASE_DIR}/signed_by_b0_mcuboot.bin"
B0_S0_HEX="${RELEASE_DIR}/signed_by_b0_mcuboot.hex"
B0_S1_BIN="${RELEASE_DIR}/signed_by_b0_mcuboot_s1_variant.bin"
B0_S1_HEX="${RELEASE_DIR}/signed_by_b0_mcuboot_s1_variant.hex"
for f in "${B0_S0_BIN}" "${B0_S0_HEX}" "${B0_S1_BIN}" "${B0_S1_HEX}"; do
    require_file "$f" "B0-signed MCUboot artifact (run sign-assemble.sh first)"
done

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

# shellcheck disable=SC1090
. "${FOTA_SIGNED}"
[ -n "${SIGN_ITEMS:-}" ] || err "${FOTA_SIGNED} has no SIGN_ITEMS"

WORK="$(mktemp -d)"; trap 'rm -rf "${WORK}"' EXIT

# Vault signature for an item -> base64 DER (strip the vault:vN: prefix).
sig_b64der() {  # <item-name>
    local v="SIGN_$1_SIG" raw
    raw="${!v-}"
    [ -n "${raw}" ] || err "no signature for '$1' in ${FOTA_SIGNED}"
    printf '%s' "${raw#vault:v*:}"
}

apply_fota_slot() {  # <rom_fixed_addr> <item> <b0_bin> <b0_hex> <out_name>
    local rom_fixed="$1" item="$2" b0_bin="$3" b0_hex="$4" out_name="$5"
    local sig="${WORK}/${out_name}.sig.b64"
    local out_bin="${RELEASE_DIR}/${out_name}.bin"
    local out_hex="${RELEASE_DIR}/${out_name}.hex"

    log "  ${out_name}: apply MCUBOOT FOTA signature (rom-fixed=${rom_fixed})"
    sig_b64der "${item}" > "${sig}"
    mcuboot_fota_fixsig "${rom_fixed}" "${sig}" "${APP_PUB}" "${b0_bin}" "${out_bin}"
    mcuboot_fota_fixsig "${rom_fixed}" "${sig}" "${APP_PUB}" "${b0_hex}" "${out_hex}"
}

log "Assembling MCUboot FOTA images (MCUBOOT key)"
apply_fota_slot "${PROV_S0_ADDR}" mcuboot_fota_s0 \
    "${B0_S0_BIN}" "${B0_S0_HEX}" "signed_by_mcuboot_and_b0_mcuboot"
apply_fota_slot "${PROV_S1_ADDR}" mcuboot_fota_s1 \
    "${B0_S1_BIN}" "${B0_S1_HEX}" "signed_by_mcuboot_and_b0_mcuboot_s1_variant"

ok "MCUboot FOTA images assembled."
log "  ${RELEASE_DIR}/signed_by_mcuboot_and_b0_mcuboot.hex/.bin"
log "  ${RELEASE_DIR}/signed_by_mcuboot_and_b0_mcuboot_s1_variant.hex/.bin"
