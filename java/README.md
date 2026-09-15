# Java ground-truth tool

Headless comparison of every named OSP solver against the SHO analytic solution — the "answer key" the Python RSI search in `../python/` is graded against but never shown.

## Dependencies (bundled, self-contained)

- `lib/osp.jar` — the Open Source Physics (OSP) numerics/framework library (GNU GPL). Copied here from the baseline app (`../baseline/FixedStepErrorLogEjsApp/lib/osp.jar`) so this tool has no dependency outside this directory.
- JDK 11+ (developed against OpenJDK 17). No other dependencies.

## Build & run

From the repo root:

```
make java-build   # javac -cp java/lib/osp.jar -d java/out java/src/*.java
make java-run     # runs SHOSolverComparison, writes results/sho_solver_comparison.csv
```

Or directly from this directory:

```
javac -cp lib/osp.jar -d out src/*.java
java -cp "out:lib/osp.jar" SHOSolverComparison
```

## Files

- `src/SHO.java` — the SHO ODE model (`x''=-kx`), implementing OSP's `ODE` interface.
- `src/CountingODE.java` — wraps an `ODE` to count derivative-evaluation calls (the `num_f_evals` cost metric).
- `src/EulerCromer.java` — hand-written Euler-Cromer solver (not bundled in `osp.jar`'s numerics package).
- `src/SHOSolverComparison.java` — runs Euler, EulerCromer, EulerRichardson, Ralston2, Heun3, RK4, Verlet, LeapFrog, Butcher5, Fehlberg8 across several step sizes and writes the comparison CSV.
