import time
from math import pi, sin, cos
from random import randrange
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.DirectGui import *
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
    self.timestep = self.timestep_slider["value"]

