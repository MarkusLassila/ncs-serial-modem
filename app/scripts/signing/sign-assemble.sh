#!/usr/bin/env bash
#
# sign-assemble.sh - apply the Vault signatures (manifest-signed.env, produced by
# sign-hashes.sh in the secure env) to the unsigned bundle and build the final
# flashable images. Runs in CI; needs the toolchain and the committed public
# keys; touches NO private key and does NOT contact Vault.
#
# Emits (under signing-out/release/): bootloader_signed.hex, app_signed.hex/.bin,
# full.hex, manifest.env. Then run package-app-fota.sh for the app FOTA package.
#
# Options:
#   --signed FILE         manifest-signed.env. Default: ${OUT_DIR}/manifest-signed.env
#   --unsigned-dir DIR    Input bundle dir.    Default: ${UNSIGNED_DIR}
#   --use-bootloader HEX  Re-sign app only and merge onto an existing signed
#                         bootloader (pair with sign-prepare.sh --app-only).

set -euo pipefail
SCRIPT_NAME="sign-assemble"
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

SIGNED="${OUT_DIR}/manifest-signed.env"
USE_BOOTLOADER=""
while [ $# -gt 0 ]; do
    case "$1" in
        --signed)         SIGNED="${2:?}"; shift 2 ;;
        --unsigned-dir)   UNSIGNED_DIR="${2:?}"; shift 2 ;;
        --use-bootloader) USE_BOOTLOADER="${2:?}"; shift 2 ;;
        -h|--help)        sed -n '2,28p' "$0"; exit 0 ;;
        *)                err "unknown argument: $1 (see --help)" ;;
    esac
done

# --- Preconditions (toolchain + committed pubkeys + signatures; no Vault) ----

require_python_imgtool
require_file "${MERGEHEX}" "mergehex.py"
require_file "${SIGNED}" "signed manifest (run sign-hashes.sh in the secure env)"
APP_PUB="$(mcuboot_pub_pem)"
require_file "${APP_PUB}" "committed MCUboot public key (certificates/)"
if [ -n "${USE_BOOTLOADER}" ]; then
    require_file "${USE_BOOTLOADER}" "reusable signed bootloader (--use-bootloader)"
else
    require_file "${VALIDATION_DATA_PY}" "validation_data.py"
    require_file "${PROVISION_PY}" "provision.py"
    NSIB_PUB="$(pub_pem "${NSIB_KEY_NAME}")"
    require_file "${NSIB_PUB}" "committed B0 public key (certificates/)"
fi

# shellcheck disable=SC1090
. "${SIGNED}"
[ -n "${SIGN_ITEMS:-}" ] || err "${SIGNED} has no SIGN_ITEMS / signatures"

U_APP="${UNSIGNED_DIR}/app_unsigned.hex"
require_file "${U_APP}" "unsigned artifact"

mkdir -p "${RELEASE_DIR}"
WORK="$(mktemp -d)"; trap 'rm -rf "${WORK}"' EXIT

# Vault signature for an item -> base64 DER (strip the vault:vN: prefix).
sig_b64der() {  # <item-name>
    local v="SIGN_$1_SIG" raw
    raw="${!v-}"
    [ -n "${raw}" ] || err "no signature for '$1' in ${SIGNED}"
    printf '%s' "${raw#vault:v*:}"
}

if [ -n "${USE_BOOTLOADER}" ]; then
    log "Assembling app only (MCUBOOT); reusing bootloader ${USE_BOOTLOADER}"
else
    log "Assembling release: NSIB=${NSIB_KEY_NAME}, MCUboot app key=${MCUBOOT_KEY_NAME}"

    U_B0="${UNSIGNED_DIR}/b0.hex"
    U_S0="${UNSIGNED_DIR}/mcuboot_s0.hex"
    U_S1="${UNSIGNED_DIR}/mcuboot_s1.hex"
    for f in "${U_B0}" "${U_S0}" "${U_S1}"; do require_file "$f" "unsigned artifact"; done

    # --- 1. B0 provisioning data (keyless) -----------------------------------
    PROV_PUBS=""
    for k in "${NSIB_KEY_NAMES[@]}"; do
        PROV_PUBS="${PROV_PUBS:+${PROV_PUBS},}$(pub_pem "$k")"
    done
    PROVISION_HEX="${RELEASE_DIR}/provision.hex"
    log "Generating B0 provisioning (provision.py) with ${#NSIB_KEY_NAMES[@]} public key(s)"
    gen_provision "${PROV_PUBS}" "${PROVISION_HEX}"

    # --- 2. Apply B0 signatures to MCUboot S0/S1 -----------------------------
    apply_mcuboot_slot() {  # <unsigned-hex> <item> <out-name>
        local in_hex="$1" item="$2" out_name="$3"
        local sigraw="${WORK}/${out_name}.sigraw"
        local out_hex="${RELEASE_DIR}/${out_name}.hex" out_bin="${RELEASE_DIR}/${out_name}.bin"
        log "  ${out_name}: apply B0 signature -> validation_data"
        der_b64_to_raw "$(sig_b64der "${item}")" "${sigraw}"
        nsib_validation "${in_hex}" "${sigraw}" "${NSIB_PUB}" "${out_hex}" "${out_bin}"
    }
    apply_mcuboot_slot "${U_S0}" nsib_s0 "signed_by_b0_mcuboot"
    apply_mcuboot_slot "${U_S1}" nsib_s1 "signed_by_b0_mcuboot_s1_variant"
fi

# --- 3. Apply the MCUBOOT signature to the application -----------------------

APP_SIG="${WORK}/app.sig.b64"
APP_HEX="${RELEASE_DIR}/app_signed.hex"; APP_BIN="${RELEASE_DIR}/app_signed.bin"
log "  app: apply MCUBOOT signature -> fix-sig"
sig_b64der app > "${APP_SIG}"
app_fixsig "${APP_SIG}" "${APP_PUB}" "${U_APP}" "${APP_HEX}"
app_fixsig "${APP_SIG}" "${APP_PUB}" "${U_APP}" "${APP_BIN}"
"${PYTHON}" "${IMGTOOL}" verify -k "${APP_PUB}" "${APP_HEX}" >/dev/null || err "app signature verification FAILED"

# --- 4. Merge: reusable bootloader, then full image --------------------------

FULL_HEX="${RELEASE_DIR}/full.hex"
if [ -n "${USE_BOOTLOADER}" ]; then
    BOOTLOADER_HEX="${USE_BOOTLOADER}"
    log "Reusing exported bootloader: ${BOOTLOADER_HEX}"
else
    BOOTLOADER_HEX="${RELEASE_DIR}/bootloader_signed.hex"
    log "Merging reusable bootloader image -> ${BOOTLOADER_HEX}"
    "${PYTHON}" "${MERGEHEX}" -o "${BOOTLOADER_HEX}" \
        "${U_B0}" "${PROVISION_HEX}" \
        "${RELEASE_DIR}/signed_by_b0_mcuboot.hex" \
        "${RELEASE_DIR}/signed_by_b0_mcuboot_s1_variant.hex"
fi
log "Merging full flashable image -> ${FULL_HEX}"
"${PYTHON}" "${MERGEHEX}" -o "${FULL_HEX}" "${BOOTLOADER_HEX}" "${APP_HEX}"

# The signed manifest is a superset of the build manifest, so it doubles as the
# manifest.env package-app-fota.sh consumes.
cp "${SIGNED}" "${RELEASE_DIR}/${MANIFEST_FILE_NAME}"

ok "Release assembled."
log "Bootloader          : ${BOOTLOADER_HEX}$([ -n "${USE_BOOTLOADER}" ] && echo ' (reused)')"
log "Signed app          : ${APP_HEX} / ${APP_BIN}"
log "Full flashable image: ${FULL_HEX}"
log "Next app FOTA package: ./package-app-fota.sh"
