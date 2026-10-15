# Methodology Notes & Camera-Ready Implementation Addenda

## 1. Edge Marginal Numerical Regularization (Finding F-09)

In `acalib/agents/belief.py` (`compute_edge_marginal`) and `acalib/alloc/aca.py` (`_compute_round_marginals`), computed edge blockage marginals $\pi_r(e)$ are regularized to $[\text{MARGINAL\_MIN}, \text{MARGINAL\_MAX}] = [0.01, 0.99]$ ($\epsilon = 0.01$).

### Rationale:
1. **Numerical Regularization**: Avoids log-likelihood singularities ($\log 0$) and division-by-zero during sequential Bayesian likelihood updates.
2. **Zero-Probability Traps**: Prevents premature absorption into degenerate certainty states ($0$ or $1$) in finite-horizon empirical simulations where adversary interdiction strategies may switch or exhibit non-stationary bursts.
3. **Behavioral Invariance**: All benchmark evaluations and frozen seeds in Protocol v5 and Protocol v6 were evaluated with this clipping in place. The values `0.01` and `0.99` are strictly preserved to maintain exact mathematical reproduction of all reported metrics.

> **Camera-Ready TODO (Post-Anonymization)**:
> In the camera-ready version of `paper.tex` (Section IV-A, Equation 4), include the clarification:
> *"Numerically, subjective edge marginals $\pi_r(e)$ are regularized to $[\epsilon, 1-\epsilon]$ with $\epsilon = 0.01$ to prevent likelihood underflow and avoid degenerate certainty states."*
