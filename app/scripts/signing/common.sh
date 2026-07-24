#!/usr/bin/env bash
#
# Shared configuration and helpers for the split build / sign / assemble flow.
# Sourced by build-unsigned.sh, sign-prepare.sh, sign-assemble.sh and
# package-app-fota.sh. Not meant to be run directly. Override any variable below
# by exporting it before calling a script.
#
# This repo NEVER contacts Vault and holds NO private keys. The flow is:
#   build-unsigned.sh  build b0/MCUboot/app, bake the MCUboot public key      (CI)
#   sign-prepare.sh    compute the hashes/digests that need signing           (CI)
#   --- carry manifest-tosign.env + sign-hashes.sh into the secure env, sign ---
#   sign-assemble.sh   apply the returned signatures -> flashable images      (CI)
#   package-app-fota.sh  wrap the signed app into dfu_application.zip         (CI)

# --- Paths -------------------------------------------------------------------

SIGN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "${SIGN_DIR}/../.." && pwd)}"
NCS_DIR="${NCS_DIR:-$(cd "${APP_DIR}/../.." && pwd)}"

BOARD="${BOARD:-nrf9151dk/nrf9151/ns}"

BUILD_DIR="${BUILD_DIR:-${APP_DIR}/build}"
CERTS_DIR="${CERTS_DIR:-${APP_DIR}/certificates}"    # committed public verification keys
OUT_DIR="${OUT_DIR:-${APP_DIR}/signing-out}"
UNSIGNED_DIR="${UNSIGNED_DIR:-${OUT_DIR}/unsigned}"  # build-unsigned.sh + sign-prepare.sh bundle
RELEASE_DIR="${RELEASE_DIR:-${OUT_DIR}/release}"     # sign-assemble.sh output (signed images)
FOTA_DIR="${FOTA_DIR:-${OUT_DIR}/fota}"              # package-app-fota.sh output
MANIFEST_FILE_NAME="manifest.env"                    # build parameters (build-unsigned.sh)
TOSIGN_FILE_NAME="manifest-tosign.env"               # build params + signing requests (sign-prepare.sh)

# --- Signing parameters (captured into the manifest) -------------------------

# --- Signing toolchain -------------------------------------------------------
# Defaults resolve inside an NCS west workspace, where build-unsigned.sh and
# sign-prepare.sh run. The assemble workflow has no west workspace and overrides
# these with a pip-installed imgtool and helper scripts fetched at NCS_REVISION.

PYTHON="${PYTHON:-python3}"
IMGTOOL="${IMGTOOL:-${NCS_DIR}/bootloader/mcuboot/scripts/imgtool.py}"
MERGEHEX="${MERGEHEX:-${SIGN_DIR}/mergehex_min.py}"
HASH_PY="${HASH_PY:-${NCS_DIR}/nrf/scripts/bootloader/hash.py}"
VALIDATION_DATA_PY="${VALIDATION_DATA_PY:-${NCS_DIR}/nrf/scripts/bootloader/validation_data.py}"
PROVISION_PY="${PROVISION_PY:-${NCS_DIR}/nrf/scripts/bootloader/provision.py}"
GENERATE_ZIP_PY="${GENERATE_ZIP_PY:-${NCS_DIR}/nrf/scripts/bootloader/generate_zip.py}"

# --- Vault key names (the actual signing happens in the secure env) ----------
# This repo does not talk to Vault. sign-prepare.sh records the KEY NAME for
# each signing request in manifest-tosign.env (e.g. SIGN_app_KEY="MCUBOOT").
# sign-hashes.sh (run in the secure env) constructs the full Vault path by
# combining the key name with VAULT_TRANSIT_MOUNT, which the operator exports
# before running sign-hashes.sh. The mount path is never stored in this repo.
NSIB_KEY_NAME="${NSIB_KEY_NAME:-B0}"             # B0 signs MCUboot S0/S1, feeds provisioning
NSIB_KEY_NAMES=("${NSIB_KEY_NAME}")              # provisioning trusted-key list (single key)
MCUBOOT_KEY_NAME="${MCUBOOT_KEY_NAME:-MCUBOOT}"  # MCUboot signs the application image
MCUBOOT_KEY_NAME_NEXT="${MCUBOOT_KEY_NAME_NEXT:-MCUBOOT_V2}"  # rotation key (next key, phase 1/2 of key rotation)

# --- Public verification keys (committed in certificates/) -------------------
# Public material only; matching private keys live in Vault. pub_pem maps a Vault
# key name to its committed PEM (B0 -> pubkey_b0.pem, MCUBOOT -> pubkey_mcuboot.pem).
pub_pem()         { echo "${CERTS_DIR}/pubkey_$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]').pem"; }
mcuboot_pub_pem() { pub_pem "${MCUBOOT_KEY_NAME}"; }

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

require_python_imgtool() {
    { [ -x "${PYTHON}" ] || command -v "${PYTHON}" >/dev/null 2>&1; } \
        || err "python interpreter not found: ${PYTHON} (set PYTHON=...)"
    require_file "${IMGTOOL}" "imgtool (set IMGTOOL=...)"
}

# --- Signing operations (no private key) -------------------------------------
# Pure, public computations shared by sign-prepare.sh (compute what to sign) and
# sign-assemble.sh (apply the returned signatures). They read build parameters
# (VAL_SKIP, MAGIC_VALUE, APP_*, PROV_*) from the sourced manifest. None of them
# touch a private key.

# imgtool 'sign' arg array (uses APP_* from the manifest) -> global APP_ARGS.
app_sign_args() {
    APP_ARGS=( sign --version "${APP_VERSION}" --slot-size "${APP_SLOT_SIZE}"
               --header-size "${APP_HEADER_SIZE}" --pad-header --align "${APP_ALIGN}" )
}

# hash.py over an unsigned MCUboot slot -> hash file (the NSIB Vault sign input).
nsib_hash() {  # <in_hex> <out_hashfile>
    "${PYTHON}" "${HASH_PY}" --in "$1" --skip "${VAL_SKIP}" > "$2"
}

# imgtool digest-to-sign for the app (needs the MCUboot PUBLIC key only).
app_digest() {  # <pubkey> <unsigned_app> <out_digest>
    app_sign_args
    "${PYTHON}" "${IMGTOOL}" "${APP_ARGS[@]}" -k "$1" --vector-to-sign digest "$2" "$3"
}

# provision.py (keyless) with a comma-separated list of public-key PEMs.
gen_provision() {  # <pubs_csv> <out_hex>
    "${PYTHON}" "${PROVISION_PY}" \
        --s0-addr "${PROV_S0_ADDR}" --s1-addr "${PROV_S1_ADDR}" \
        --provision-addr "${PROV_ADDR}" \
        --public-key-files "$1" --output "$2" --max-size "${PROV_MAX_SIZE}" \
        --num-counter-slots-version "${PROV_COUNTER_SLOTS}" \
        --otp-write-width "${PROV_OTP_WIDTH}"
}

# Vault DER signature (base64, prefix already stripped) -> raw r||s 64-byte file.
der_b64_to_raw() {  # <der_b64> <out_rawfile>
    printf '%s' "$1" | base64 -d | "${PYTHON}" -c '
import sys
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
r, s = decode_dss_signature(sys.stdin.buffer.read())
sys.stdout.buffer.write(r.to_bytes(32, "big") + s.to_bytes(32, "big"))' > "$2"
    [ "$(wc -c < "$2" | tr -d ' ')" = "64" ] || err "expected 64-byte raw NSIB signature ($2)"
}

# validation_data.py: embed an NSIB raw signature into validation data.
nsib_validation() {  # <in_hex> <raw_sigfile> <pubkey> <out_hex> <out_bin>
    "${PYTHON}" "${VALIDATION_DATA_PY}" \
        --input "$1" --skip "${VAL_SKIP}" --offset "${VAL_OFFSET}" \
        --signature "$2" --public-key "$3" --magic-value "${MAGIC_VALUE}" \
        --output-hex "$4" --output-bin "$5"
}

# imgtool --fix-sig: apply an app signature (base64 DER file) to the unsigned app.
app_fixsig() {  # <sig_b64der_file> <pubkey> <unsigned_app> <out>
    app_sign_args
    "${PYTHON}" "${IMGTOOL}" "${APP_ARGS[@]}" --fix-sig "$1" --fix-sig-pubkey "$2" "$3" "$4"
}

# imgtool 'sign' arg array for the MCUboot FOTA (signed_by_mcuboot_and_b0) path.
# Takes a per-slot rom-fixed address. MCUboot binaries already have CONFIG_ROM_START_OFFSET
# header space reserved, so --pad-header is not needed.
mcuboot_fota_sign_args() {  # <rom_fixed_addr>
    MCUBOOT_FOTA_ARGS=( sign --version "${MCUBOOT_VERSION}"
                        --slot-size "${MCUBOOT_SLOT_SIZE}"
                        --header-size "${MCUBOOT_HEADER_SIZE}"
                        --align "${MCUBOOT_ALIGN}"
                        --rom-fixed "$1" )
}

# imgtool digest for a B0-signed MCUboot slot (needs the MCUboot PUBLIC key only).
mcuboot_fota_digest() {  # <rom_fixed_addr> <pubkey> <b0_signed_bin> <out_digest>
    mcuboot_fota_sign_args "$1"
    "${PYTHON}" "${IMGTOOL}" "${MCUBOOT_FOTA_ARGS[@]}" -k "$2" --vector-to-sign digest "$3" "$4"
}

# imgtool --fix-sig for a MCUboot FOTA slot (applies a pre-computed signature).
mcuboot_fota_fixsig() {  # <rom_fixed_addr> <sig_b64der_file> <pubkey> <b0_signed_in> <out>
    mcuboot_fota_sign_args "$1"
    "${PYTHON}" "${IMGTOOL}" "${MCUBOOT_FOTA_ARGS[@]}" \
        --fix-sig "$2" --fix-sig-pubkey "$3" "$4" "$5"
}
