#!/usr/bin/env bash
#
# sign-hashes.sh - THE ONLY STEP THAT RUNS IN THE SECURE ENVIRONMENT.
#
# Reads the prepared hashes from manifest-tosign.env (produced by sign-prepare.sh
# in CI), signs each one with Vault, and writes the signatures into
# manifest-signed.env. That is all it does: a few `vault write` calls over opaque
# base64 inputs. Bring manifest-signed.env back to CI and run the assemble
# workflow (sign-assemble.sh) to build the flashable images.
#
# Dependencies: the `vault` CLI and an authenticated Vault session. NO Python, no
# toolchain, no NCS scripts, no network beyond Vault. This file is self-contained
# - it is the only thing (besides manifest-tosign.env) that needs to live in the
# secure environment.
#
# Vault credentials are NOT managed here: authenticate first (VAULT_ADDR set,
# `vault login`, and VAULT_CACERT if your Vault uses a private CA).
#
# Usage:
#   sign-hashes.sh --in manifest-tosign.env --out manifest-signed.env

set -euo pipefail

IN=""
OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --in)      IN="${2:?}"; shift 2 ;;
        --out)     OUT="${2:?}"; shift 2 ;;
        -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
        *)         echo "sign-hashes: unknown argument: $1" >&2; exit 1 ;;
    esac
done

die() { echo "sign-hashes: error: $*" >&2; exit 1; }

[ -n "${IN}" ]  || die "missing --in <manifest-tosign.env>"
[ -n "${OUT}" ] || die "missing --out <manifest-signed.env>"
[ -f "${IN}" ]  || die "input not found: ${IN}"
command -v vault >/dev/null 2>&1 || die "the 'vault' CLI is required"
vault token lookup >/dev/null 2>&1 || die \
"no authenticated Vault session. Authenticate first, e.g.:
       export VAULT_ADDR=https://vault.example.com
       export VAULT_CACERT=/path/to/ca.crt      # if Vault uses a private CA
       vault login"

# Load the requests (SIGN_ITEMS + per-item SIGN_<name>_* variables).
# shellcheck disable=SC1090
. "${IN}"
[ -n "${SIGN_ITEMS:-}" ] || die "${IN} has no SIGN_ITEMS (was it produced by sign-prepare.sh?)"

# Carry the whole to-sign manifest through, then append the signatures.
cp "${IN}" "${OUT}"
{
    echo ""
    echo "# === signatures (sign-hashes.sh) ==="
} >> "${OUT}"

ind() { local v="$1"; printf '%s' "${!v-}"; }   # indirect read of variable named $1

for item in ${SIGN_ITEMS}; do
    path="$(ind "SIGN_${item}_PATH")"
    b64="$(ind "SIGN_${item}_INPUT_B64")"
    prehashed="$(ind "SIGN_${item}_PREHASHED")"
    halg="$(ind "SIGN_${item}_HASH_ALGORITHM")"
    marsh="$(ind "SIGN_${item}_MARSHALING")"
    [ -n "${path}" ] && [ -n "${b64}" ] || die "request '${item}' is incomplete in ${IN}"

    args=( "input=${b64}" "hash_algorithm=${halg:-sha2-256}" "marshaling_algorithm=${marsh:-asn1}" )
    [ "${prehashed}" = "true" ] && args+=( "prehashed=true" )

    echo "  signing ${item} with ${path}" >&2
    sig="$(vault write -field=signature "${path}" "${args[@]}")" \
        || die "vault sign failed for ${item} (${path})"
    [ -n "${sig}" ] || die "vault returned an empty signature for ${item}"
    echo "SIGN_${item}_SIG=\"${sig}\"" >> "${OUT}"
done

echo "sign-hashes: signed ${SIGN_ITEMS} -> ${OUT}" >&2
