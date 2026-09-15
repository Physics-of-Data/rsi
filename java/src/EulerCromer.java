import org.opensourcephysics.numerics.AbstractODESolver;
import org.opensourcephysics.numerics.ODE;

/**
 * Euler-Cromer (semi-implicit Euler): update velocity from the old position,
 * then update position from the just-updated velocity. Not bundled in osp.jar's
 * numerics package, so implemented by hand as one of the RSI discovery targets
 * that a plain (non-partitioned) Runge-Kutta tableau cannot reach.
 */
public class EulerCromer extends AbstractODESolver {
    private double[] rate;

    public EulerCromer(ODE ode) {
        super(ode);
    }

    public double step() {
        double[] state = ode.getState();
        if (rate == null) {
            rate = new double[state.length];
        }
        ode.getRate(state, rate);
        state[1] += stepSize * rate[1]; // v_{n+1} = v_n + h * a(x_n)
        ode.getRate(state, rate);
        state[0] += stepSize * rate[0]; // x_{n+1} = x_n + h * v_{n+1}
        state[2] += stepSize;
        return stepSize;
    }
}
