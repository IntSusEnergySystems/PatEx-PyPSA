# Environment for the soft-link on the CÉCI cluster nic6: source it on the login node and
# in every job. Code and PatEx bundles in $HOME/CAN-CLIMACT, PyPSA-Eur and its pixi env on
# scratch (it writes data/, resources/, results/ in the repository).
export PATH=$HOME/.pixi/bin:$PATH
export PIXI_CACHE_DIR=$GLOBALSCRATCH/.cache/pixi
export RATTLER_CACHE_DIR=$GLOBALSCRATCH/.cache/rattler
export UV_CACHE_DIR=$GLOBALSCRATCH/.cache/uv
export XDG_CACHE_HOME=$GLOBALSCRATCH/.cache
export CAN=$GLOBALSCRATCH/CAN-CLIMACT
# Gurobi: token license of the cluster (server on nic5), used by the env's gurobipy.
export GRB_LICENSE_FILE=/opt/cecisw/arch/2025b/software/Gurobi/13.0.1-GCCcore-14.3.0/gurobi.lic
