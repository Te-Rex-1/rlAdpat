'''
Author : Tej Patel
Contact: tej18121995@gmail.com
'''

from __future__ import absolute_import, print_function
from sumolib import checkBinary

import os
import sys
import optparse
import random
import traci
import numpy as np
import keras
import h5py
from collections import deque
from keras.layers import Input, Conv2D, Flatten, Dense
from keras.models import Model
import matplotlib.pyplot as plt

# Global lists for realtime plotting of vehicle queue data
steps_before = []   # simulation steps at which we record "before" queue values
queue_before = []   # corresponding queue counts before action
steps_after = []    # simulation steps at which we record "after" queue values
queue_after = []    # corresponding queue counts after action

# Setup realtime plotting
plt.ion()  # interactive mode on
fig, ax = plt.subplots()
line_before, = ax.plot(steps_before, queue_before, 'b-', label='Queue Before Action')
line_after, = ax.plot(steps_after, queue_after, 'r-', label='Queue After Action')
ax.set_xlabel("Simulation Step")
ax.set_ylabel("Vehicle Queue (Halting Vehicles)")
ax.legend()
plt.title("Real-time Vehicle Queue Monitoring")

def update_plot():
    """Update the realtime plot lines."""
    line_before.set_data(steps_before, queue_before)
    line_after.set_data(steps_after, queue_after)
    ax.relim()
    ax.autoscale_view()
    plt.draw()
    plt.pause(0.001)

def record_vehicle_queue(step, filename):
    """Log vehicle queue count into a file and return the value."""
    queue_count = (traci.edge.getLastStepHaltingNumber('1si') +
                   traci.edge.getLastStepHaltingNumber('2si') +
                   traci.edge.getLastStepHaltingNumber('3si') +
                   traci.edge.getLastStepHaltingNumber('4si'))
    with open(filename, "a") as log_file:
        log_file.write("Step {}: Queue = {}\n".format(step, queue_count))
    return queue_count


class DQNAgent:
    def __init__(self):
        self.gamma = 0.95   # discount rate
        self.epsilon = 0.1  # exploration rate
        self.learning_rate = 0.0002
        self.memory = deque(maxlen=200)
        self.model = self._build_model()
        self.action_size = 2

    def _build_model(self):
        # Neural Net for Deep-Q learning Model
        input_1 = Input(shape=(12, 12, 1))
        x1 = Conv2D(16, (4, 4), strides=(2, 2), activation='relu')(input_1)
        x1 = Conv2D(32, (2, 2), strides=(1, 1), activation='relu')(x1)
        x1 = Flatten()(x1)

        input_2 = Input(shape=(12, 12, 1))
        x2 = Conv2D(16, (4, 4), strides=(2, 2), activation='relu')(input_2)
        x2 = Conv2D(32, (2, 2), strides=(1, 1), activation='relu')(x2)
        x2 = Flatten()(x2)

        input_3 = Input(shape=(2, 1))
        x3 = Flatten()(input_3)

        x = keras.layers.concatenate([x1, x2, x3])
        x = Dense(128, activation='relu')(x)
        x = Dense(64, activation='relu')(x)
        x = Dense(2, activation='linear')(x)

        model = Model(inputs=[input_1, input_2, input_3], outputs=[x])
        model.compile(optimizer=keras.optimizers.RMSprop(lr=self.learning_rate), loss='mse')
        return model

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        if np.random.rand() <= self.epsilon:
            return random.randrange(self.action_size)
        act_values = self.model.predict(state)
        return np.argmax(act_values[0])  # returns action

    def replay(self, batch_size):
        minibatch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state, done in minibatch:
            target = reward
            if not done:
                target = (reward + self.gamma * np.amax(self.model.predict(next_state)[0]))
            target_f = self.model.predict(state)
            target_f[0][action] = target
            self.model.fit(state, target_f, epochs=1, verbose=0)

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)


class SumoIntersection:
    def __init__(self):
        # Import modules from the $SUMO_HOME/tools directory
        try:
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', "tools"))
            sys.path.append(os.path.join(os.environ.get("SUMO_HOME", os.path.join(os.path.dirname(__file__), "..", "..", "..")), "tools"))
            from sumolib import checkBinary  # noqa
        except ImportError:
            sys.exit("please declare environment variable 'SUMO_HOME' as the root directory of your sumo installation (it should contain folders 'bin', 'tools' and 'docs')")

    def generate_routefile(self):
        random.seed(42)  # make tests reproducible
        N = 3600  # number of time steps
        # Demand per second from different directions
        pH = 1. / 7
        pV = 1. / 11
        pAR = 1. / 30
        pAL = 1. / 25
        with open("input_routes.rou.xml", "w") as routes:
            print('''<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="SUMO_DEFAULT_TYPE" accel="0.8" decel="4.5" sigma="0"
    length="5" minGap="2" maxSpeed="70"/>
    <route id="always_right" edges="1fi 1si 4o 4fi 4si 2o 2fi 2si 3o 3fi 3si 1o 1fi"/>
    <route id="always_left" edges="3fi 3si 2o 2fi 2si 4o 4fi 4si 1o 1fi 1si 3o 3fi"/>
    <route id="horizontal" edges="2fi 2si 1o 1fi 1si 2o 2fi"/>
    <route id="vertical" edges="3fi 3si 4o 4fi 4si 3o 3fi"/>
    ''', file=routes)
            vehNr = 0
            for i in range(N):
                if random.uniform(0, 1) < pH:
                    print('    <vehicle id="right_%i" type="SUMO_DEFAULT_TYPE" route="horizontal" depart="%i" />' % (vehNr, i), file=routes)
                    vehNr += 1
                if random.uniform(0, 1) < pV:
                    print('    <vehicle id="left_%i" type="SUMO_DEFAULT_TYPE" route="vertical" depart="%i" />' % (vehNr, i), file=routes)
                    vehNr += 1
                if random.uniform(0, 1) < pAL:
                    print('    <vehicle id="down_%i" type="SUMO_DEFAULT_TYPE" route="always_left" depart="%i" color="1,0,0"/>' % (vehNr, i), file=routes)
                    vehNr += 1
                if random.uniform(0, 1) < pAR:
                    print('    <vehicle id="down_%i" type="SUMO_DEFAULT_TYPE" route="always_right" depart="%i" color="1,0,0"/>' % (vehNr, i), file=routes)
                    vehNr += 1
            print("</routes>", file=routes)

    def get_options(self):
        optParser = optparse.OptionParser()
        optParser.add_option("--nogui", action="store_true",
                             default=False, help="run the commandline version of sumo")
        options, args = optParser.parse_args()
        return options

    def getState(self):
        positionMatrix = []
        velocityMatrix = []
        cellLength = 7
        offset = 11
        speedLimit = 14

        junctionPosition = traci.junction.getPosition('0')[0]
        vehicles_road1 = traci.edge.getLastStepVehicleIDs('1si')
        vehicles_road2 = traci.edge.getLastStepVehicleIDs('2si')
        vehicles_road3 = traci.edge.getLastStepVehicleIDs('3si')
        vehicles_road4 = traci.edge.getLastStepVehicleIDs('4si')
        for i in range(12):
            positionMatrix.append([0]*12)
            velocityMatrix.append([0]*12)
        for v in vehicles_road1:
            ind = int(abs((junctionPosition - traci.vehicle.getPosition(v)[0] - offset)) / cellLength)
            if ind < 12:
                positionMatrix[2 - traci.vehicle.getLaneIndex(v)][11 - ind] = 1
                velocityMatrix[2 - traci.vehicle.getLaneIndex(v)][11 - ind] = traci.vehicle.getSpeed(v) / speedLimit
        for v in vehicles_road2:
            ind = int(abs((junctionPosition - traci.vehicle.getPosition(v)[0] + offset)) / cellLength)
            if ind < 12:
                positionMatrix[3 + traci.vehicle.getLaneIndex(v)][ind] = 1
                velocityMatrix[3 + traci.vehicle.getLaneIndex(v)][ind] = traci.vehicle.getSpeed(v) / speedLimit
        junctionPosition = traci.junction.getPosition('0')[1]
        for v in vehicles_road3:
            ind = int(abs((junctionPosition - traci.vehicle.getPosition(v)[1] - offset)) / cellLength)
            if ind < 12:
                positionMatrix[6 + 2 - traci.vehicle.getLaneIndex(v)][11 - ind] = 1
                velocityMatrix[6 + 2 - traci.vehicle.getLaneIndex(v)][11 - ind] = traci.vehicle.getSpeed(v) / speedLimit
        for v in vehicles_road4:
            ind = int(abs((junctionPosition - traci.vehicle.getPosition(v)[1] + offset)) / cellLength)
            if ind < 12:
                positionMatrix[9 + traci.vehicle.getLaneIndex(v)][ind] = 1
                velocityMatrix[9 + traci.vehicle.getLaneIndex(v)][ind] = traci.vehicle.getSpeed(v) / speedLimit
        light = [1, 0] if traci.trafficlight.getPhase('0') == 4 else [0, 1]
        position = np.array(positionMatrix).reshape(1, 12, 12, 1)
        velocity = np.array(velocityMatrix).reshape(1, 12, 12, 1)
        lgts = np.array(light).reshape(1, 2, 1)
        return [position, velocity, lgts]


if __name__ == '__main__':
    sumoInt = SumoIntersection()
    options = sumoInt.get_options()

    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')
    sumoInt.generate_routefile()

    # Parameters for training
    episodes = 2000
    batch_size = 32

    agent = DQNAgent()
    try:
        agent.load('Models/reinf_traf_control.h5')
    except Exception as e:
        print('No models found: ', e)

    for e in range(episodes):
        stepz = 0
        waiting_time = 0
        reward1 = 0
        reward2 = 0
        action = 0

        # Start the simulation
        traci.start([sumoBinary, "-c", "cross3ltl.sumocfg", '--start'])
        traci.trafficlight.setPhase("0", 0)
        traci.trafficlight.setPhaseDuration("0", 200)

        while traci.simulation.getMinExpectedNumber() > 0 and stepz < 7000:
            # Record and update realtime graph BEFORE taking an action
            q_before = record_vehicle_queue(stepz, "queue_before_action.txt")
            steps_before.append(stepz)
            queue_before.append(q_before)
            update_plot()

            traci.simulationStep()
            state = sumoInt.getState()
            action = agent.act(state)
            light = state[2]

            # Depending on action and current light phase, execute control logic.
            if action == 0 and light[0][0][0] == 0:
                # (For branch: action 0 when light phase is 0)
                for i in range(6):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 1)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 2)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                for i in range(6):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 3)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                # Execute action
                reward1 = traci.edge.getLastStepVehicleNumber('1si') + traci.edge.getLastStepVehicleNumber('2si')
                reward2 = traci.edge.getLastStepHaltingNumber('3si') + traci.edge.getLastStepHaltingNumber('4si')
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 4)
                    reward1 += traci.edge.getLastStepVehicleNumber('1si') + traci.edge.getLastStepVehicleNumber('2si')
                    reward2 += traci.edge.getLastStepHaltingNumber('3si') + traci.edge.getLastStepHaltingNumber('4si')
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                # Record AFTER action data and update realtime graph
                q_after = record_vehicle_queue(stepz, "queue_after_action.txt")
                steps_after.append(stepz)
                queue_after.append(q_after)
                update_plot()

            elif action == 0 and light[0][0][0] == 1:
                # (For branch: action 0 when light phase is 1)
                reward1 = traci.edge.getLastStepVehicleNumber('1si') + traci.edge.getLastStepVehicleNumber('2si')
                reward2 = traci.edge.getLastStepHaltingNumber('3si') + traci.edge.getLastStepHaltingNumber('4si')
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 4)
                    reward1 += traci.edge.getLastStepVehicleNumber('1si') + traci.edge.getLastStepVehicleNumber('2si')
                    reward2 += traci.edge.getLastStepHaltingNumber('3si') + traci.edge.getLastStepHaltingNumber('4si')
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                q_after = record_vehicle_queue(stepz, "queue_after_action.txt")
                steps_after.append(stepz)
                queue_after.append(q_after)
                update_plot()

            elif action == 1 and light[0][0][0] == 0:
                # (For branch: action 1 when light phase is 0)
                reward1 = traci.edge.getLastStepVehicleNumber('4si') + traci.edge.getLastStepVehicleNumber('3si')
                reward2 = traci.edge.getLastStepHaltingNumber('2si') + traci.edge.getLastStepHaltingNumber('1si')
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 0)
                    reward1 += traci.edge.getLastStepVehicleNumber('4si') + traci.edge.getLastStepVehicleNumber('3si')
                    reward2 += traci.edge.getLastStepHaltingNumber('2si') + traci.edge.getLastStepHaltingNumber('1si')
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                q_after = record_vehicle_queue(stepz, "queue_after_action.txt")
                steps_after.append(stepz)
                queue_after.append(q_after)
                update_plot()

            elif action == 1 and light[0][0][0] == 1:
                # (For branch: action 1 when light phase is 1)
                for i in range(6):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 5)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 6)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                for i in range(6):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 7)
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                reward1 = traci.edge.getLastStepVehicleNumber('4si') + traci.edge.getLastStepVehicleNumber('3si')
                reward2 = traci.edge.getLastStepHaltingNumber('2si') + traci.edge.getLastStepHaltingNumber('1si')
                for i in range(10):
                    stepz += 1
                    traci.trafficlight.setPhase('0', 0)
                    reward1 += traci.edge.getLastStepVehicleNumber('4si') + traci.edge.getLastStepVehicleNumber('3si')
                    reward2 += traci.edge.getLastStepHaltingNumber('2si') + traci.edge.getLastStepHaltingNumber('1si')
                    waiting_time += (traci.edge.getLastStepHaltingNumber('1si') +
                                     traci.edge.getLastStepHaltingNumber('2si') +
                                     traci.edge.getLastStepHaltingNumber('3si') +
                                     traci.edge.getLastStepHaltingNumber('4si'))
                    traci.simulationStep()
                q_after = record_vehicle_queue(stepz, "queue_after_action.txt")
                steps_after.append(stepz)
                queue_after.append(q_after)
                update_plot()

            new_state = sumoInt.getState()
            reward = reward1 - reward2
            agent.remember(state, action, reward, new_state, False)
            if len(agent.memory) > batch_size:
                agent.replay(batch_size)

        # Mark the last transition as terminal
        mem = agent.memory[-1]
        del agent.memory[-1]
        agent.memory.append((mem[0], mem[1], reward, mem[3], True))
        print('episode - ' + str(e) + ' total waiting time - ' + str(waiting_time))
        traci.close(wait=False)
    sys.stdout.flush()
    plt.ioff()
    plt.show()
