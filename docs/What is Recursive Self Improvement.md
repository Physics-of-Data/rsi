---
date: 2026-09-14
tags: [rsi, recursive-self-improvement, pareto-frontier, physics, obsidian]
---
# Recursive Self Improvement — session transcript

## *User*
*I keep reading about Recursive Self Improvement or RSI. What is exactly? Show me with a practical example what RSI can do*

## Assistant

**Recursive self-improvement (RSI)** is when a system improves its own ability to improve itself — not just getting better at a task, but getting better at *getting better*. Each improvement makes the next improvement easier or faster, which can create a feedback loop (the "intelligence explosion" idea from I.J. Good and later Bostrom).

The key distinction: a chess engine that gets better at chess isn't RSI. A system that rewrites its own training code, search algorithm, or architecture — and that rewrite makes it *more capable of rewriting itself well next time* — is RSI.

**A concrete practical example — an automated ML research loop:**

Imagine an AI system tasked with "improve your own training pipeline":

1. **Baseline**: It starts with a model and its own training code (data loader, optimizer settings, architecture).
2. **Self-analysis**: It profiles its own training run, finds the optimizer is wasting compute on redundant gradient steps.
3. **Self-modification**: It rewrites the optimizer code, tests the change, measures a real speedup (say, 15% faster convergence).
4. **Compounding**: Because it now trains faster, it can run *more experiments per hour* — including experiments on how to search for further improvements. It discovers a better way to search its own codebase for bottlenecks.
5. **Loop**: Step 4's improvement makes step 5 faster too, and so on.

This is roughly what systems like **AutoML-Zero**, **STOP** (Self-Taught Optimizer), and the more recent **Darwin Gödel Machine** experiment with — an agent that edits its own code, benchmarks the edited version against the original, and keeps the edit only if it scores higher, then repeats on the new version.

The practical caveat: real RSI loops today are narrow and bounded — they improve one metric (training speed, benchmark score) within a fixed problem space, not general intelligence. The "explosion" scenario people worry about requires the loop to generalize across domains without hitting diminishing returns, which hasn't been demonstrated. Current systems plateau — each round of self-improvement yields smaller gains until the loop stalls.

## *User*
> [!quote] *Current systems plateau — each round of self-improvement yields smaller gains until the loop stalls.*

*I have seen that in optimization. You can optimize a system while there is room to optimize, then, naturally plateaus the system becomes stable and no more gains are possible.*

## Assistant
That's exactly the right intuition, and it's worth being precise about why plateaus happen in ordinary optimization, because it clarifies where the RSI worry either holds or breaks down.

**Why normal optimization plateaus:** You're searching within a fixed space — fixed parameters, fixed architecture, fixed problem formulation. Diminishing returns set in because you're squeezing out the last inefficiencies in a bounded system. Once you hit the Pareto frontier of that space, further tuning just trades one variable against another. This is thermodynamics-flavored: entropy, noise floors, hardware limits.

**Where RSI is a different animal (in theory):** The concerning version of RSI isn't optimizing *within* a fixed space — it's a system that can change the *shape of the search space itself*. Instead of "tune the hyperparameters," it's "rewrite the algorithm that does the tuning," or "redesign the architecture that the algorithm runs on." Each of those moves can, in principle, open up a *new* region of possibility that wasn't reachable before — so the plateau of one regime becomes the starting point of a new one, rather than a hard ceiling.

Concretely: your optimization plateau is like exhausting local search in one basin. RSI's theoretical worry is a system that can occasionally jump to a *better basin* — and if jumping-to-better-basins is itself a skill that improves with practice, the plateaus get higher over time instead of flat.

**Why this hasn't actually happened yet, in practice:** Every real self-improving system we have (AutoML-Zero, STOP, Darwin Gödel Machine, etc.) still plateaus, for reasons that map onto your intuition:

- The "meta" level (the thing doing the improving) is itself bounded — by compute, by the quality of its own evaluation signal, by the model's own reasoning ceiling. You can't out-search a search process smarter than yourself using a dumber one.
- Basin-jumps in practice are rare and usually still human-discovered (new architectures, new training objectives) rather than machine-discovered.
- Evaluation itself gets harder as the system improves — you need better benchmarks to detect better systems, and benchmark quality doesn't automatically self-improve alongside the system.

So the honest empirical answer today looks like your optimization case: plateaus, not explosions. The theoretical disagreement in the field is entirely about whether that's a permanent feature of these systems or just where our current techniques happen to top out.

[[What is Pareto Frontier]]

## *User*
*Back to RSI, I am interested in running an experiment. I prefer it is a physics problem. How could I assemble the experiment so it self improves itself without intervention?*

## Assistant
A clean physics testbed for this is **integrator self-improvement on a chaotic system** — say, a double pendulum or a three-body orbit. It's good because you have a genuinely measurable "better": energy conservation error over a long simulation, with no ambiguity about what counts as improvement.

**The loop, structured so it runs unattended:**

1. **Fixed problem, fixed ground truth.** Pick the system (e.g. Earth-Moon-Sun three-body problem). Define the fitness metric precisely — total energy drift after N steps, or deviation from a high-precision reference solution. This has to be automatic and numeric; no human judging outputs.

2. **A mutable "solver" component.** Start with something crude — explicit Euler integration. Represent its knobs (step size, method choice, order) as parameters a script can programmatically change.

3. **Self-modification step.** Each generation, the loop mutates the solver: tries a different step size, swaps Euler for a symplectic integrator, adjusts adaptive step-size thresholds. Score each variant against the fitness metric. Keep whatever improves it, discard the rest — this is just hill-climbing or a small genetic algorithm at this point, not yet RSI.

4. **The recursive part — improve the improver.** This is what separates it from plain hyperparameter search: let the *mutation strategy itself* be tunable and scored. If large random mutations keep failing, the loop should shrink mutation size; if a certain family of mutations (e.g. "try symplectic methods") keeps winning, it should search that family harder. Track meta-statistics (success rate per mutation type) and let the loop reweight its own search policy based on those stats — no human tuning the tuner.

5. **Termination logic, tied to what we discussed on plateaus.** Log fitness-per-generation. Have the loop auto-stop (or downshift into a different mutation family) when improvement rate falls below a threshold for K consecutive generations — this is where you'll *empirically watch it plateau*, and you can test whether letting it switch integrator families (Euler → RK4 → symplectic → adaptive symplectic) pushes the plateau higher, which is the "new basin" idea from earlier.

**Practically implementing "without intervention":** this is just a script — a `for generation in range(N)` loop in Python (scipy/numpy for the integrators) that logs results to a file and runs unattended on a schedule or in one long batch job. You don't need an LLM in the loop at all for this version; it's closer to evolutionary computation. If you want an LLM agent doing the mutating (actually rewriting solver *code*, not just parameters — closer to Darwin Gödel Machine style RSI), that's a bigger lift: you'd want Claude Code driving it, with a harness that runs each candidate, scores it, and commits only improvements — and that needs sandboxing since an agent editing its own solver code unsupervised can produce broken or divergent code.

Given your OSP/Java simulation work, this could plug directly into your existing Java physics engine as the "problem" being solved, with a Python (or shell) wrapper doing the outer mutate-test-keep loop.

## *User*
*I have all the elements or objects. It is how build the infinite loop what the problem is.*

## Assistant
The core design problem is state: the loop needs to persist everything about itself between iterations, including its own strategy for iterating, so it never needs a human to restart or reset it. Here's the skeleton:

**Loop architecture**

```
state = load_checkpoint() or init_state()
# state = { solver_params, mutation_policy, history[], generation }

while not stop_condition(state):
    candidates = propose_mutations(state.solver_params, state.mutation_policy)
    results = [evaluate(c) for c in candidates]  # run + score fitness

    best = select_best(results, state.solver_params)
    state.solver_params = best.params

    state.mutation_policy = update_policy(state.mutation_policy, results)
    state.history.append(best.fitness)
    state.generation += 1

    save_checkpoint(state)   # <- this line is what makes it unattended
    log(state)
```

**The four things that make it actually run "without intervention":**

1. **Checkpointing every iteration, not just at the end.** If the process dies (OOM, crash, power loss), it resumes from the last saved `state`, not from scratch. This is the difference between a loop and a script you have to babysit.

2. **`stop_condition` is internal, not a human watching a graph.** Something like: stop after `N` generations, or after `K` consecutive generations with fitness improvement below `epsilon` (your plateau detector from before). Without this, "infinite loop" is literal and just burns compute forever.

3. **`update_policy` is where the self-improvement lives**, not in `select_best`. Selecting the best mutation each round is just hill-climbing. What makes it recursive is that `mutation_policy` — the thing deciding *how to propose the next mutations* — also gets rewritten based on `results`. E.g. track a success rate per mutation type in `state.mutation_policy`, and bias future proposals toward whatever's been paying off.

4. **A hard resource ceiling**, independent of `stop_condition`. Wall-clock timeout or max-generation cap enforced by the outer runner (cron, systemd timer, or just `timeout 6h python loop.py`), so a bug in your stop logic can't spin forever unattended.

**Practically for your setup:** this is one long-running Python process (or a shell loop calling your Java OSP integrator as a subprocess each generation), with `state` serialized to JSON or pickle after every generation. Nothing fancier is needed — no database, no LLM in the loop, unless you want the mutation step to be "rewrite this solver's source code" rather than "tweak these numeric params," in which case propose_mutations becomes a Claude Code call instead of a numpy perturbation, and evaluate needs a sandboxed subprocess with a timeout so a broken candidate can't hang the whole loop.

Want me to sketch the concrete Python version wired to a double pendulum, so you have something runnable to start from?

## *User*
*No, not yet. I am on my iPad, not my PC.*
*I wanted to start the conversation. Your pseudo code was very helpful.*
*A silly example could be finding the best integrator for a given differential equation. Starts with simplest and discovers itself RK4.*

## Assistant
That's actually a great toy example — not silly at all. It's got everything: a clean fitness metric (local truncation error, or global error against a known analytical solution), a discrete search space (Euler → midpoint → RK4 → adaptive RK45 → symplectic variants), and enough structure that you can literally watch it climb the "order of accuracy" ladder step by step.

The nice part for demonstrating RSI specifically (not just optimization) is if you don't hand it "try RK4" as a candidate — you hand it *primitives* (like "you can add an intermediate evaluation point" or "you can combine two estimates at different step sizes") and let the mutation policy discover that stacking several of those primitives in a particular pattern reconstructs something RK4-shaped on its own. That's the difference between "search a menu" and "search the space that contains the menu" — closer to real self-improvement than picking from a known list.

When you're back on the PC, that's a good starting point.

## *User*
*I don't want to give it a menu of solvers like Euler, Verlet, RK4, etc. I want the RSI to discover them.*

## Assistant
That's the right instinct — a menu of named solvers turns this into selection, not discovery. To make actual discovery possible, you need to go down one level: give it the **primitive operations** integrators are built from, not the integrators themselves.

**What the "genome" should be**

An integrator, stripped to its bones, is a recipe for combining derivative evaluations. So the building blocks are things like:

- Evaluate the derivative at a point (given current state, or a state offset by some fraction of the step)
- Take a weighted combination of previously computed evaluations
- Use that combination to step the state forward

If you represent a candidate integrator as a small graph or sequence of these operations — "evaluate at `t`, evaluate at `t + a·h` using a combination of prior evaluations, evaluate at `t + b·h`, combine all evaluations with weights `w1, w2, w3`, step forward" — then Euler, the midpoint method, and RK4 aren't separate menu items. They're specific settings of *how many evaluation points* and *what weights*. RK4 is a particular 4-stage, specifically-weighted instance of this general template (this general template is literally called a **Runge-Kutta tableau** — worth knowing the term, since it's exactly the representation you want: an array of coefficients `a_ij`, `b_i`, `c_i` that *is* the genome).

**What mutation operates on**

- Add or remove an evaluation stage
- Perturb the coefficients (`a_ij`, `b_i`, `c_i`) that say where each stage samples and how stages get combined
- (Optionally, for symplectic methods) constrain mutations to preserve some structural property, like the sum of weights equaling 1

**Why this actually lets RK4 "emerge"**

Because RK4's coefficients are a known optimum for 4th-order accuracy per unit cost, a fitness-driven search over tableau space should converge toward that region on its own — you never told it "RK4 is the answer," you gave it the space that contains it, plus the pressure that finds it. If it converges near the classical RK4 tableau, that's genuine evidence the search works, since you can check the discovered coefficients against the textbook ones.

**The honest caveat**

This is now a much harder search — continuous coefficient optimization over a space with many equivalent or near-equivalent solutions, not picking from five named options. It's more likely to rediscover *a* good 4-stage method than land exactly on textbook RK4's specific coefficients (there are whole families of order-4 tableaux). That's actually fine, even more interesting — it shows the search finding *a* good solution rather than memorizing *the* one you had in mind.

