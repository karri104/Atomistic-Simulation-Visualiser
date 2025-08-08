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
from PyQt6 import QtWidgets, QtCore, QtGui


def startStopSimulation(panda):
    if panda.pause_flag:
        panda.pause_flag = False
        # Re-add the moveAtomsTask to task manager
        panda.taskMgr.add(panda.moveAtomsTask, "MoveAtomsTask")
    else:
        panda.pause_flag = True

def changeSpeed(panda, label, v):
    panda.timestep = v
    label.setText(f"Simulation Speed: {panda.timestep:.2f}")

def changeThermo(panda, label, v):
    # Change thermal endpoint and update fix
    panda.tStop = 2**(v/1000)
    panda.lmp.command(f"fix 2 all langevin {panda.tStart} {panda.tStop} 0.1 102938")
    label.setText(f"Thermostat: {panda.tStop:.3f}")
    # Update tStart to be the thermal endpoint of last simulation. This approach
    # might lead to some funkiness if tStop was not reached in previous simulation
    panda.tStart = panda.tStop

def changeBaro(panda, label, v):
    panda.pStop = v/100000
    panda.lmp.command(f"fix 3 all nph couple xyz iso {panda.pStart} {panda.pStop} 1")
    label.setText(f"Barostat: {panda.pStop:.3f}")
    panda.pStart = panda.pStop

def extractThermo(panda):
    # Store thermo data from last simulation
    last_thermo = panda.lmp.last_thermo()
    last_thermo = {k.upper():v for k,v in last_thermo.items()}
    for key in last_thermo:
        panda.sim_info[key].append(last_thermo[key])

def toggleGraphView(main_window, graph_name, state):
    if state == 2:
        main_window.graphs[graph_name].setVisible(False)
    elif state == 0:
        main_window.graphs[graph_name].setVisible(True)


