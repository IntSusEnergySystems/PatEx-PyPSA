#!/bin/bash
# Run the PyPSA-Eur workflow (PatEx soft-link) inside one Slurm job on nic6.
#
#   CONFIGS="config/config.patex.yaml config/patex/<run>.yaml" \
#   sbatch --cpus-per-task=34 --mem=64000M --time=1-12:00:00 pypsa_job.sh [snakemake args]
#
# Resources are given on the sbatch line (nic6: at most 1900 MB per core). Snakemake
# uses all the job's cores and keeps 2 GB of the job's memory free. Extra arguments go
# to snakemake (e.g. a target, or `--omit-from solve_network` for the preparation job).
#SBATCH --job-name=patex-pypsa
#SBATCH --partition=batch
#SBATCH --ntasks=1
#SBATCH --output=%x-%j.out
set -euo pipefail

: "${CONFIGS:?set CONFIGS to the snakemake config files}"
source "$HOME/CAN-CLIMACT/PATEX2PYPSA/PATEX_PyPSA/scripts/cluster/nic6_env.sh"
cd "$CAN/PyPSA-Eur-CANEU"

mem_mb=$(( SLURM_MEM_PER_NODE - 2000 ))
echo "job $SLURM_JOB_ID on $(hostname): $SLURM_CPUS_PER_TASK cores, ${mem_mb} MB for snakemake"
echo "configs: $CONFIGS; git $(git rev-parse --short HEAD)"

srun --cpus-per-task="$SLURM_CPUS_PER_TASK" pixi run --frozen snakemake \
    --configfile $CONFIGS \
    --cores "$SLURM_CPUS_PER_TASK" --resources mem_mb="$mem_mb" \
    --rerun-incomplete --keep-going --printshellcmds "$@"
