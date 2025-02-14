import time
from math import pi, sin, cos
from random import randrange
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.DirectGui import *
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
# Change this panda3d.core import to be more specific
from panda3d.core import *
from lammps import lammps, LMP_TYPE_VECTOR, LMP_STYLE_ATOM, LMP_TYPE_ARRAY
import numpy as np

def startStopSimulation(self):
    if self.pause_flag:
        self.pause_flag = False
        # Re-add the moveAtomsTask to task manager
        self.taskMgr.add(self.moveAtomsTask, "MoveAtomsTask")
    else:
        self.pause_flag = True

def changeSpeed(self):
    self.timestep = self.delayTime_slider["value"]

def changeThermo(self):
    # Change thermal endpoint and update fix
    self.tStop = self.thermo_slider["value"]
    self.lmp.command(f"fix 2 all langevin {self.tStart} {self.tStop} 0.1 102938")
    # Update tStart to be the thermal endpoint of last simulation. This approach
    # might lead to some funkiness if tStop was not reached in previous simulation
    self.tStart = self.tStop

def extractThermo(self):
    # Store thermo data from last simulation
    last_thermo = self.lmp.last_thermo()
    cull = False
    # Check if there's already max amount of data stored, if so enable cull flag to delete the first entry in each keyword
    if len(self.sim_info["Step"]) >= self.info_size:
        cull = True
    for key in last_thermo:
        if cull:
            del self.sim_info[key][0]
        self.sim_info[key].append(last_thermo[key])
    print(self.sim_info)

def createPlots(self):
    fig, ax = plt.subplots()
    graph = ax.plot(self.sim_info["Step"],self.sim_info["Temp"], color='b')[0]
    return fig

def update(frame, self):
    global graph
    graph.set_xdata(self.sim_info["Step"])
    graph.set_ydata(self.sim_info["Temp"])
    plt.xlim(self.sim_info["Step"][0], self.sim_info["Step"][-1])

