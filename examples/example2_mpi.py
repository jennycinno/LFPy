#!/usr/bin/env python
'''
################################################################################
#
# This is an example scripts using LFPy with an active cell model adapted from
# Mainen and Sejnowski, Nature 1996, for the original files, see
# http://senselab.med.yale.edu/modeldb/ShowModel.asp?model=2488
#
# This scripts is set up to use the model, where the active conductances are set
# in the file "active_declarations_example2.hoc", and uses the mechanisms from
# the .mod-files provided here. For this example to work, run "nrnivmodl" in
# this folder to compile these mechanisms
# (i.e. /$PATHTONEURON/nrn/x86_64/bin/nrnivmodl).
#
# A single excitatory synapse drive the neuron into producing a single action-
# potential, and the local field potential are calculated on a dense 2D-grid
# on around the soma.
#
# This file is based on the example2.py file, but uses MPI to split
# up the LFP-calculations, by calculating the LFP in different coordinates
# on different MPI ranks, and then collecting results in the end
#
# To run using MPI, type
# mpirun -np 2 python example2_mpi.py
#
################################################################################
'''

#import some plotting stuff and the LFPy-module
import numpy as np
import matplotlib.pyplot as plt
from mpi4py import MPI
import LFPy

#MPI stuff we're using
COMM = MPI.COMM_WORLD
SIZE = COMM.Get_size()
RANK = COMM.Get_rank()

################################################################################
# Define parameters, using dictionaries
# It is possible to set a few more parameters for each class or functions, but
# we chose to show only the most important ones here.
################################################################################

#define cell parameters used as input to cell-class
cellParameters = {
    'morphology' : 'morphologies/L5_Mainen96_wAxon_LFPy.hoc',
    'rm' : 30000,               # membrane resistance
    'cm' : 1.0,                 # membrane capacitance
    'Ra' : 150,                 # axial resistance
    'v_init' : -65,             # initial crossmembrane potential
    'e_pas' : -65,              # reversal potential passive mechs
    'passive' : True,           # switch on passive mechs
    'nsegs_method' : 'lambda_f',# method for setting number of segments,
    'lambda_f' : 500,           # segments are isopotential at this frequency
    'timeres_NEURON' : 2**-5,   # dt of LFP and NEURON simulation.
    'timeres_python' : 2**-5,
    'tstartms' : -10,           #start time, recorders start at t=0
    'tstopms' : 10,             #stop time of simulation
    'custom_code'  : ['active_declarations_example2.hoc'], # will run this file
}

#Synaptic parameters, corresponding to a NetCon synapse built into NEURON
synapseParameters = {
    'idx' : 0,               # insert synapse on index "0", the soma
    'e' : 0.,                # reversal potential of synapse
    'syntype' : 'Exp2Syn',   # conductance based double-exponential synapse
    'tau1' : 1.0,            # Time constant, rise
    'tau2' : 1.0,            # Time constant, decay
    'weight' : 0.03,         # Synaptic weight
    'record_current' : True, # Will enable synapse current recording
}

#Generate the grid in xz-plane over which we calculate local field potentials
X, Z = np.mgrid[-5:6, -5:6] * 10
Y = np.zeros(X.shape)

#define parameters for extracellular recording electrode, using optional method
electrodeParameters = {
    'sigma' : 0.3,                  # extracellular conductivity
    'x' : X.flatten()[RANK::SIZE],  # x,y,z-coordinates of contact points
    'y' : Y.flatten()[RANK::SIZE],  # performing some fancy slice operation
    'z' : Z.flatten()[RANK::SIZE],  # to distribute with MPI
    'method' : 'som_as_point',  #treat soma segment as sphere source
}

################################################################################
# Main simulation procedure, setting up extracellular electrode, cell, synapse
################################################################################

#create extracellular electrode object
electrode = LFPy.RecExtElectrode(**electrodeParameters)

#Initialize cell instance, using the LFPy.Cell class
cell = LFPy.Cell(**cellParameters)
#set the position of midpoint in soma to Origo (not needed, this is the default)
cell.set_pos(xpos = 0, ypos = 0, zpos = 0)
#rotate the morphology 90 degrees around z-axis
cell.set_rotation(z = np.pi/2)

#attach synapse with parameters and set spike time
synapse = LFPy.Synapse(cell, **synapseParameters)
synapse.set_spike_times(np.array([1]))

#perform NEURON simulation, results saved as attributes in the cell instance
cell.simulate(electrode = electrode, rec_isyn=True)

#Create a container for the results
results = []
#collect LFPs and contact coordinates from other RANKS
if RANK == 0:
    for i in xrange(1, SIZE):
        result = COMM.recv(source=MPI.ANY_SOURCE)   #receive from ANY RANK
        results.append(result)      #collect
else:
    result = [electrode.x, electrode.y, electrode.z, electrode.LFP]
    COMM.send(result, dest=0)      #send to RANK 0
    results = None                 #results only exist on RANK 0
    electrode = None               #not needed more in this case

COMM.Barrier()                          #sync MPI threads

if RANK == 0:
    #putting results into the electrode object
    #Note that this do not put arrays in the same order as example2.py
    for result in results:
        electrode.x = np.r_[electrode.x, result[0]]
        electrode.y = np.r_[electrode.y, result[1]]
        electrode.z = np.r_[electrode.z, result[2]]
        electrode.LFP = np.r_[electrode.LFP, result[3]]
    
    # Plotting of simulation results:
    from example_suppl import plot_ex2
    fig = plot_ex2(cell, electrode)
    #Optional: saving the figure
    #fig.savefig('example2_mpi.pdf')
    
    plt.show()

else:
    pass
