import org.opensourcephysics.numerics.*;

import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;

/**
 * Headless ground-truth comparison: runs the SHO problem through every named
 * OSP solver (plus hand-written EulerCromer) at several step sizes, scoring
 * against the closed-form analytic solution the same way the baseline
 * FixedStepErrorLogEjsApp's error table does (x error, energy error, both
 * absolute and relative). This is the "answer key" the RSI-discovered
 * tableaux will later be graded against -- it is never shown to the search.
 */
public class SHOSolverComparison {

    static final double k = 1.0;
    static final double x0 = 1.0;
    static final double v0 = 0.0;
    static final double omega = Math.sqrt(k);
    static final double A = Math.sqrt(x0 * x0 + (v0 / omega) * (v0 / omega));
    static final double phi = Math.atan2(-v0 / omega, x0);
    static final double E_ANALYTIC = 0.5 * v0 * v0 + 0.5 * k * x0 * x0;

    static double analyticX(double t) {
        return A * Math.cos(omega * t + phi);
    }

    public static void main(String[] args) throws IOException {
        double[] dts = {0.1, 0.05, 0.01};
        double T = 18.0;

        Map<String, Function<ODE, ODESolver>> solvers = new LinkedHashMap<>();
        solvers.put("Euler", Euler::new);
        solvers.put("EulerCromer", EulerCromer::new);
        solvers.put("EulerRichardson", EulerRichardson::new);
        solvers.put("Ralston2", Ralston2::new);
        solvers.put("Heun3", Heun3::new);
        solvers.put("RK4", RK4::new);
        solvers.put("Verlet", Verlet::new);
        solvers.put("LeapFrog", LeapFrog::new);
        solvers.put("Butcher5", Butcher5::new);
        solvers.put("Fehlberg8", Fehlberg8::new);

        String[] header = {"solver", "dt", "num_f_evals", "num_steps", "final_t",
                "x_numeric", "x_analytic", "abs_dx", "rel_dx",
                "E_numeric", "E_analytic", "abs_dE", "rel_dE",
                "rms_dx", "rms_dE"};

        StringBuilder console = new StringBuilder();
        console.append(String.format(Locale.US, "%-15s %6s %10s %8s %12s %12s %12s %12s%n",
                "solver", "dt", "f_evals", "steps", "abs_dx", "rel_dx", "abs_dE", "rel_dE"));

        try (PrintWriter csv = new PrintWriter(new FileWriter("/storage/develop/rsi/results/sho_solver_comparison.csv"))) {
            csv.println(String.join(",", header));

            for (Map.Entry<String, Function<ODE, ODESolver>> entry : solvers.entrySet()) {
                String name = entry.getKey();
                for (double dt : dts) {
                    SHO sho = new SHO(x0, v0, k);
                    CountingODE counting = new CountingODE(sho);
                    ODESolver solver = entry.getValue().apply(counting);
                    solver.initialize(dt);

                    int numSteps = (int) Math.round(T / dt);
                    double sumSqDx = 0, sumSqDE = 0;

                    for (int i = 0; i < numSteps; i++) {
                        solver.step();
                        double[] state = sho.getState();
                        double t = state[2];
                        double xA = analyticX(t);
                        double EN = 0.5 * state[1] * state[1] + 0.5 * k * state[0] * state[0];
                        double dx = state[0] - xA;
                        double dE = EN - E_ANALYTIC;
                        sumSqDx += dx * dx;
                        sumSqDE += dE * dE;
                    }

                    double[] finalState = sho.getState();
                    double finalT = finalState[2];
                    double xA = analyticX(finalT);
                    double EN = 0.5 * finalState[1] * finalState[1] + 0.5 * k * finalState[0] * finalState[0];
                    double absDx = Math.abs(finalState[0] - xA);
                    double absDE = Math.abs(EN - E_ANALYTIC);
                    double relDx = Math.abs(xA) > 1e-12 ? absDx / Math.abs(xA) : absDx;
                    double relDE = Math.abs(E_ANALYTIC) > 1e-12 ? absDE / Math.abs(E_ANALYTIC) : absDE;
                    double rmsDx = Math.sqrt(sumSqDx / numSteps);
                    double rmsDE = Math.sqrt(sumSqDE / numSteps);

                    csv.println(String.join(",",
                            name, String.valueOf(dt), String.valueOf(counting.count),
                            String.valueOf(numSteps), String.valueOf(finalT),
                            String.valueOf(finalState[0]), String.valueOf(xA),
                            String.valueOf(absDx), String.valueOf(relDx),
                            String.valueOf(EN), String.valueOf(E_ANALYTIC),
                            String.valueOf(absDE), String.valueOf(relDE),
                            String.valueOf(rmsDx), String.valueOf(rmsDE)));

                    console.append(String.format(Locale.US,
                            "%-15s %6.3f %10d %8d %12.4e %12.4e %12.4e %12.4e%n",
                            name, dt, counting.count, numSteps, absDx, relDx, absDE, relDE));
                }
            }
        }

        System.out.print(console);
        System.out.println("\nCSV written to /storage/develop/rsi/results/sho_solver_comparison.csv");
    }
}
