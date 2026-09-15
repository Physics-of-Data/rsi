import org.opensourcephysics.numerics.ODE;

/**
 * Simple harmonic oscillator: x'' = -k x, state = {x, v, t}.
 * Matches the baseline FixedStepErrorLogEjsApp's own SHO parameterization.
 */
public class SHO implements ODE {
    private final double[] state = new double[3]; // x, v, t
    private final double k;

    public SHO(double x0, double v0, double k) {
        state[0] = x0;
        state[1] = v0;
        state[2] = 0.0;
        this.k = k;
    }

    public double[] getState() {
        return state;
    }

    public void getRate(double[] state, double[] rate) {
        rate[0] = state[1];
        rate[1] = -k * state[0];
        rate[2] = 1.0;
    }
}
