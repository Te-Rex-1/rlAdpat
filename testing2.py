'''
Real-time Simulation: 7000 Steps with Queue vs Time Graph

Ensure that the SUMO_HOME environment variable is set and that you have a valid SUMO configuration file
(e.g., "cross3ltl.sumocfg"). Adjust the edge IDs (e.g., '1si', '2si', etc.) to match your network.
'''

from __future__ import absolute_import, print_function
import os
import sys
import optparse
import traci
import numpy as np
import matplotlib.pyplot as plt
from sumolib import checkBinary

def get_vehicle_queue():
    """
    Compute the total number of halting vehicles from the designated edges.
    Modify the edge IDs as required.
    """
    q = (traci.edge.getLastStepHaltingNumber('1si') +
         traci.edge.getLastStepHaltingNumber('2si') +
         traci.edge.getLastStepHaltingNumber('3si') +
         traci.edge.getLastStepHaltingNumber('4si'))
    return q

def run_simulation(steps_limit=7000):
    # Parse SUMO options
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="run the commandline version of sumo")
    options, args = optParser.parse_args()

    # Select SUMO binary
    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')

    # Set your SUMO configuration file (change if necessary)
    sumoConfig = "cross3ltl.sumocfg"

    # Start SUMO as a subprocess
    traci.start([sumoBinary, "-c", sumoConfig, "--start"])

    # Prepare real-time plotting
    plt.ion()  # interactive mode on
    fig, ax = plt.subplots()
    x_data = []
    y_data = []
    line, = ax.plot(x_data, y_data, 'b-', label='Queue')
    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Vehicle Queue (Halting Vehicles)")
    ax.set_title("Real-time Vehicle Queue vs Time")
    ax.legend()

    # Run simulation loop for steps_limit steps or until simulation ends
    for step in range(steps_limit):
        traci.simulationStep()
        queue_val = get_vehicle_queue()
        x_data.append(step)
        y_data.append(queue_val)
        line.set_data(x_data, y_data)
        ax.relim()
        ax.autoscale_view()
        plt.draw()
        plt.pause(0.001)  # pause briefly for plot update

    traci.close()
    plt.ioff()
    plt.show()

if __name__ == '__main__':
    run_simulation(7000)
