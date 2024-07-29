import time
from math import pi, sin, cos
from random import randrange
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.interval.IntervalGlobal import Sequence
# Change this panda3d.core import to be more specific
from panda3d.core import *
from lammps import lammps, LMP_TYPE_VECTOR, LMP_STYLE_ATOM, LMP_TYPE_ARRAY
import numpy as np


class MyApp(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        # Create lammps object and get initial coords
        self.lmp = lammps()
        self.lmp.file("../inputs/read_from_file.in")
        self.x = self.lmp.numpy.extract_atom("x")
        self.ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)

        self.atom_count = self.lmp.get_natoms()
        self.atoms = []
        self.atom_ids = self.lmp.numpy.extract_atom("id")
        # delayTime determines how long each timestep takes
        self.delayTime = 1

        # Add templates for different atoms. Add more or change values depending on amount of atoms in simulation
        self.atom_types = {1: {"color": [0.9, 0.9, 0.9], "scale": [0.1, 0.1, 0.1]},
                           2: {"color": [0.9, 0.0, 0.0], "scale": [0.15, 0.15, 0.15]}}
        self.atom_type_list = self.lmp.numpy.extract_atom("type")

        # Create pointlight to make atom details visible
        plight1 = PointLight('plight1')
        plight1.setColor((0.7, 0.7, 0.7, 1))
        plnp1 = self.render.attachNewNode(plight1)
        plnp1.setPos(100, 100, 100)
        self.render.setLight(plnp1)

        # Create second pointlight to make the "dark side" brighter
        plight2 = PointLight('plight2')
        plight2.setColor((0.7, 0.7, 0.7, 1))
        plnp2 = self.render.attachNewNode(plight2)
        plnp2.setPos(-100, -100, -100)
        self.render.setLight(plnp2)

        # Create ambientlight to make things more visible
        alight = AmbientLight('alight')
        alight.setColor((0.4, 0.4, 0.4, 1))
        alnp = self.render.attachNewNode(alight)
        self.render.setLight(alnp)

        print("Creating atoms...")
        # Add the createAtomsTask to task manager
        self.taskMgr.add(self.createAtomsTask, "CreateAtomsTask")

        # Add the moveAtomsTask to task manager
        self.taskMgr.add(self.moveAtomsTask, "MoveAtomsTask")

        # Add the drawSimulationBoxTask to task manager
        self.taskMgr.add(self.drawSimulationBoxTask, "DrawSimulationBoxTask")

        # print("Setting up the camera...")
        # Add the spinCameraTask to task manager
        # self.taskMgr.add(self.spinCameraTask, "SpinCameraTask")


    def createAtomsTask(self, task):
        for atom_id in self.atom_ids:
            # Load atom model. If simulation has a lot of atoms or needs to run very quickly,
            # change the model to a lower poly version, which can be found online. Any .egg file should work.
            atom = self.loader.loadModel('../models/Sphere_HighPoly.egg')
            # Reparent to render (important to do this so the model can be rendered)'
            atom.reparentTo(self.render)
            if self.atom_type_list[atom_id - 1] in self.atom_types.keys():
                atom.setColor(self.atom_types[self.atom_type_list[atom_id - 1]]["color"][0],
                              self.atom_types[self.atom_type_list[atom_id - 1]]["color"][1],
                              self.atom_types[self.atom_type_list[atom_id - 1]]["color"][2], 1)
                atom.setScale(self.atom_types[self.atom_type_list[atom_id - 1]]["scale"][0],
                              self.atom_types[self.atom_type_list[atom_id - 1]]["scale"][1],
                              self.atom_types[self.atom_type_list[atom_id - 1]]["scale"][2])
            # Give atoms random positions
            atom.setPos(self.x[atom_id - 1][0], self.x[atom_id - 1][1], self.x[atom_id - 1][2])
            # Add atoms to a list, so they can be easily accessed later
            self.atoms.append(atom)
        return Task.done


    def drawSimulationBoxTask(self, task):
        lines = LineSegs()

        # bottom face
        p = np.zeros(3)
        lines.moveTo(p[0], p[1], p[2])
        for i in [1, 2, -1, -2]: # 1==x, 2==y, 3==z
            p += np.sign(i) * self.cell[abs(i)-1,:]
            lines.drawTo(p[0], p[1], p[2])

        # support sides
        for b in [[], [0], [1], [0,1]]: # base point cell vector combinations
            p = np.zeros(3)
            for v in b:
                p += self.cell[v, :]

            lines.moveTo(p[0], p[1], p[2])
            p += self.cell[2, :]
            lines.drawTo(p[0], p[1], p[2])

        # top face
        p = self.cell[2,:]
        lines.moveTo(p[0], p[1], p[2])
        for i in [1, 2, -1, -2]: # 1==x, 2==y, 3==z
            p += np.sign(i) * self.cell[abs(i)-1,:]
            lines.drawTo(p[0], p[1], p[2])

        lines.setThickness(4)
        node = lines.create()
        nodepath = NodePath(node)
        nodepath.reparentTo(render)

        return Task.done


    def moveAtomsTask(self, task):
        starttime = time.monotonic()
        self.run_single()

        for i in range(self.atom_count):
            new_pos = (self.ix[i,:]-self.ix_old[i,:]) @ self.cell + self.x[i,:]

            posInterval = self.atoms[i].posInterval(self.delayTime, Point3(new_pos[0], new_pos[1], new_pos[2]),
                                           Point3(self.x_old[i,0], self.x_old[i,1], self.x_old[i,2]))
            posInterval.start()
        self.taskMgr.doMethodLater(self.delayTime - (time.monotonic() - starttime), self.moveAtomsTask, "MoveAtomsTask")
        return Task.done


    def run_single(self):
        # store old values for reference
        self.x_old = self.x.copy()
        self.ix_old = self.ix.copy()
        self.xu_old = self.xu.copy()

        # Run single timestep and get ids and coords of atoms
        self.lmp.command("run 10")

        boxlo, boxhi, xy, yz, xz, periodicity, box_change = self.lmp.extract_box()
        cell = np.zeros((3,3))
        np.fill_diagonal(cell, np.array(boxhi)-np.array(boxlo))
        cell[1,0] = xy
        cell[2,0] = xz
        cell[2,1] = yz
        self.cell = cell

        atom_ids = self.lmp.numpy.extract_atom("id")
        x = self.lmp.numpy.extract_atom("x")
        ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)

        x_sorted = np.zeros(x.shape)
        ix_sorted = np.zeros(ix.shape)
        xu_sorted = np.zeros(xu.shape)
        for i in range(len(atom_ids)):
            x_sorted[atom_ids[i]-1, :] = x[i, :]
            ix_sorted[atom_ids[i]-1, :] = ix[i, :]
            xu_sorted[atom_ids[i]-1, :] = xu[i, :]

        self.x = x_sorted
        self.ix = ix_sorted
        self.xu = xu_sorted

"""
    def spinCameraTask(self, task):
        angleDegrees = task.time * 6.0
        angleRadians = angleDegrees * pi / 180.0
        self.camera.setPos(30 * sin(angleRadians), -30 * cos(angleRadians), 0)
        self.camera.setHpr(angleDegrees, 0, 0)
        return Task.cont
"""



if __name__ == "__main__":
    app = MyApp()
    app.run()
