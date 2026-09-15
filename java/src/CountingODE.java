import org.opensourcephysics.numerics.ODE;

/** Wraps an ODE to count derivative-oracle calls (num_f_evals) per solver run. */
public class CountingODE implements ODE {
    private final ODE inner;
    public int count = 0;

    public CountingODE(ODE inner) {
        this.inner = inner;
    }

    public double[] getState() {
        return inner.getState();
    }

    public void getRate(double[] state, double[] rate) {
        count++;
        inner.getRate(state, rate);
    }
}
