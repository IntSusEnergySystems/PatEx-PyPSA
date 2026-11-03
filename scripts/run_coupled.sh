#!/usr/bin/env bash
# Run PatEx, export the PatEx → PyPSA-Eur coupling bundle, optionally run PyPSA-Eur.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: run_coupled.sh <coupling_dir> [--snakemake] [snakemake args...]

1. If <coupling_dir>/patex/run.pkl is missing, run PatEx (in the patex uv env) for
   $PATEX_REGIONS ("|"-separated, e.g. "AT|BE|DE"; default BE) on $PATEX_DATASET,
   with levers from <coupling_dir>/patex/levers.json if present.
2. Export <coupling_dir>/pypsa_inputs with patex-pypsa.
3. With --snakemake, run pypsa-eur with config/config.patex.yaml and
   coupling_dir=<coupling_dir> (remaining args forwarded to snakemake).

Environment: PATEX_DATASET (required for step 1), PATEX_REGIONS,
HORIZONS (default 2030,2040,2050), EXPORT_ARGS (extra patex-pypsa options,
e.g. "--strict" or "--allow-negative" for the synthetic dataset), PATEX_ROOT, PYPSA_ROOT.
EOF
}

[[ $# -lt 1 || "$1" == "-h" || "$1" == "--help" ]] && { usage; exit 0; }

mkdir -p "$1/patex"
COUPLING_DIR="$(realpath "$1")"
shift

RUN_SNAKEMAKE=false
SNAKEMAKE_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --snakemake) RUN_SNAKEMAKE=true ;;
        *) SNAKEMAKE_ARGS+=("$1") ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINK_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PATEX_ROOT="${PATEX_ROOT:-$(realpath "${LINK_ROOT}/../../patex")}"
PYPSA_ROOT="${PYPSA_ROOT:-$(realpath "${LINK_ROOT}/../../PyPSA-Eur-CANEU")}"
HORIZONS="${HORIZONS:-2030,2040,2050}"
RUN_PKL="${COUPLING_DIR}/patex/run.pkl"

# the dataset is also needed by the export (CO2 factors)
: "${PATEX_DATASET:?set PATEX_DATASET (dataset version dir or s3:// URI)}"
if [[ ! -f "${RUN_PKL}" ]]; then
    LEVERS=()
    [[ -f "${COUPLING_DIR}/patex/levers.json" ]] && LEVERS=(--levers-file "${COUPLING_DIR}/patex/levers.json")
    echo "Running PatEx for ${PATEX_REGIONS:-BE} on ${PATEX_DATASET}"
    (cd "${PATEX_ROOT}" && uv run patex run "${PATEX_REGIONS:-BE}" \
        --dataset "${PATEX_DATASET}" "${LEVERS[@]}" -o "${RUN_PKL}")
fi

echo "Exporting coupling bundle to ${COUPLING_DIR}/pypsa_inputs"
(cd "${PATEX_ROOT}" && uv run --with-editable "${LINK_ROOT}" patex-pypsa export-coupling \
    --pkl "${RUN_PKL}" --coupling-dir "${COUPLING_DIR}" --horizons "${HORIZONS}" \
    --dataset "${PATEX_DATASET}" ${EXPORT_ARGS:-})
(cd "${PATEX_ROOT}" && uv run --with-editable "${LINK_ROOT}" patex-pypsa report \
    --coupling-dir "${COUPLING_DIR}")
echo "Report: ${COUPLING_DIR}/report/index.html"

if [[ "${RUN_SNAKEMAKE}" != true ]]; then
    echo "Export complete. Pass --snakemake to run pypsa-eur."
    exit 0
fi

cd "${PYPSA_ROOT}"
pixi run snakemake \
    --configfile config/config.patex.yaml \
    --config "patex={coupling_dir: ${COUPLING_DIR}}" \
    "${SNAKEMAKE_ARGS[@]}"
