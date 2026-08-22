import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brian2 import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from MultiCompartmentalModel import Model

FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'figures')

def main():
    print("Starting Brian 2 Migration Test...")
    
    # 1. Initialize our modernized model
    model = Model()
    
    # 2. Setup a single neuron with 2 dendritic branches for testing
    print("Building model components...")
    model.p['num_DendEach'] = 2
    model.make_model(num_soma=1, condition='invitro', record_all=True)
    
    # 3. Create input pathways (Pathway A and B)
    # Poisson inputs
    print("Creating inputs...")
    P_A = PoissonGroup(10, rates=30*Hz)
    P_B = PoissonGroup(10, rates=30*Hz)
    
    # 4. Connect pathways to dendrites using our Option B native plasticity synapses
    print("Connecting plastic synapses...")
    # Pathway A to Dendrite 0
    syn_A = model.add_plastic_synapses(P_A, model.n['Dend'][0:1], p_connect=1.0)
    # Pathway B to Dendrite 1
    syn_B = model.add_plastic_synapses(P_B, model.n['Dend'][1:2], p_connect=1.0)
    
    model.add([P_A, P_B, syn_A, syn_B])
    
    # Track weights
    mon_w_A = StateMonitor(syn_A, 'w', record=True, dt=100*ms)
    mon_w_B = StateMonitor(syn_B, 'w', record=True, dt=100*ms)
    model.add([mon_w_A, mon_w_B])
    
    # 5. Run simulation
    print("Running simulation (this will trigger Brian 2 compilation)...")
    model.run(1.0 * second, report='text')
    
    # 6. Plot the results to verify basic connectivity and plasticity compilation
    print("Simulation finished. Generating validation plot...")
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.plot(model.mon['MvSoma'].t / ms, model.mon['MvSoma'].V[0] / mV)
    plt.xlabel('Time (ms)')
    plt.ylabel('Soma Voltage (mV)')
    plt.title('Somatic Activity')
    
    plt.subplot(1, 2, 2)
    plt.plot(mon_w_A.t / ms, mon_w_A.w[0], label='Path A (Dend 0)')
    plt.plot(mon_w_B.t / ms, mon_w_B.w[0], label='Path B (Dend 1)')
    plt.xlabel('Time (ms)')
    plt.ylabel('Synaptic Weight')
    plt.title('Plasticity Trace')
    plt.legend()
    
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, 'v2_migration_test.png')
    plt.savefig(out)
    print(f"Success! Test figure saved to {out}")

if __name__ == '__main__':
    main()
