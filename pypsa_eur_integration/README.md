# PatEx demands in PyPSA-Eur: the hooks

The hooks are applied on branch `develop` of the fork
[`IntSusEnergySystems/PyPSA-Eur-CANEU`](https://github.com/IntSusEnergySystems/PyPSA-Eur-CANEU)
(`../../PyPSA-Eur-CANEU`), all behind `patex.enable` (default `false`). The list of
changes and their reasons is in [../MODEL_CHANGES.md](../MODEL_CHANGES.md); the code
itself lives only in the fork.

Prerequisite in the pixi env (it has no pip):

```bash
cd ../../PyPSA-Eur-CANEU
uv pip install --python .pixi/envs/default/bin/python --no-deps -e ../PATEX2PYPSA/PATEX_PyPSA
```

Redo it after any `pixi install` that recreates the env. `patex_pypsa` is imported only
when `patex.enable` is true.

Check after a run (pixi python):

```bash
python ../PATEX2PYPSA/PATEX_PyPSA/scripts/check_network_ledger.py \
    results/<run>/networks/solved_<h>.nc ../PATEX2PYPSA/runs/<scenario> --horizon <h> \
    --heating-efficiencies resources/<run>/heating_efficiencies.csv
```
