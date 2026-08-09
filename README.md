# Thalamocortical Gating & Cognitive Flexibility Model

This repository contains the computational neuroscience models extending the pathway-specific dendritic gating mechanism of [Yang et al. (2016)](https://www.nature.com/articles/nn.4303) to investigate the Mediodorsal Thalamic (MD) drive and E/I balance hypothesis proposed by Zhang (2025).

By modeling the MD thalamus' projections to both Somatostatin (SOM) gating circuits (via VIP interneurons) and somatic excitability circuits (via PV interneurons), this model demonstrates how thalamocortical drive can act as a "meta-controller" for cognitive flexibility and pathway-specific plasticity in the prefrontal cortex (PFC).

## Project Structure

- `src/v2/` - Contains the core modular Brian 2 codebase:
  - `MultiCompartmentalModel.py` - Core Pyramidal and Interneuron multi-compartment structure.
  - `equations.py` - Membrane voltage ODEs and Graupner-Brunel plasticity rules.
  - `parameters.py` - Comprehensive biological parameters (conductances, delays, thresholds).
- `validate_model.py` - Automated verification test suite for basic model sanity checks (6/6 tests).
- `demo_v2_zhang2025.py` - Context-switching simulation demonstrating how MD thalamic drive switches learning pathways.
- `sweep_phase_diagram.py` - 2D parameter sweep script exploring MD→PV vs. MD→VIP weights to map out healthy cognitive flexibility vs. "Schizophrenic" pathology.
- `generate_network_synapse_figure.py` - Script to generate high-quality figures of the network and synaptic architecture.
- `print_network_summary.py` - A lightweight script that prints a formatted live inspection of the Brian 2 Network and synaptic equations.
- `figures/` - Generated output plots (e.g., Phase Diagram, Calcium Plasticity).

## Installation

1. Create a Python 3 virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

**1. View Network Architecture & Equations**
To view a text-based summary of the network and the exact Brian 2 differential equations:
```bash
python print_network_summary.py
```

**2. Run Core Simulation**
To run the main simulation testing context-switching and MD drive:
```bash
python demo_v2_zhang2025.py
```

**3. Run Verification Tests**
To ensure the multi-compartmental parameters and integration stability are correct:
```bash
python validate_model.py
```

**4. Generate Phase Diagram**
To run the full 2D parameter sweep over Thalamocortical weight drives (this takes ~15-20 minutes depending on your CPU):
```bash
python sweep_phase_diagram.py
```



## Modeling Details

- **Pyramidal Neurons:** Modeled using a 2-layer multi-compartmental reduction (1 soma, 30 independent dendritic branches) connected via Ohmic axial coupling.
- **Interneurons:** Parvalbumin (PV) cells control somatic output. Somatostatin (SOM) cells gate individual dendrites. Vasoactive Intestinal Peptide (VIP) cells inhibit SOM to open the gate.
- **Plasticity:** Synapses use the calcium-based Graupner-Brunel bistable double-well plasticity model. Long-Term Potentiation (LTP) only occurs when dendritic branches are disinhibited, permitting NMDA-receptor magnesium unblocking and subsequent large calcium transients.

## Reference
- **Yang et al. 2016:** "A dendritic disinhibitory circuit mechanism for pathway-specific gating"
- **Zhang 2025:** MD Thalamocortical drive, E/I imbalance, and context learning.
