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
import random


def startStopSimulation(panda):
    if panda.pause_flag:
        panda.pause_flag = False
        # Re-add the moveAtomsTask to task manager
        panda.taskMgr.add(panda.moveAtomsTask, "MoveAtomsTask")
    else:
        panda.pause_flag = True

def changeSpeed(panda, v):
    panda.timestep = v

def changeThermo(panda, v):
    # Change thermal endpoint and update fix
    panda.tStop = 2**v
    panda.lmp.command(f"fix 2 all langevin {panda.tStart} {panda.tStop} 0.1 102938")
    # Update tStart to be the thermal endpoint of last simulation. This approach
    # might lead to some funkiness if tStop was not reached in previous simulation
    panda.tStart = panda.tStop

def extractThermo(panda):
    # Store thermo data from last simulation
    last_thermo = panda.lmp.last_thermo()
    cull = False
    # Check if there's already max amount of data stored, if so enable cull flag to delete the first entry in each keyword
    if len(panda.sim_info["Step"]) >= panda.info_size:
        cull = True
    for key in last_thermo:
        if cull:
            del panda.sim_info[key][0]
        panda.sim_info[key].append(last_thermo[key])





