import sys, time
from PyQt6 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.DirectGui import *
# Change this panda3d.core import to be more specific
from panda3d.core import *
from math import pi, sin, cos
from random import randrange
from lammps import lammps, LMP_TYPE_VECTOR, LMP_STYLE_ATOM, LMP_TYPE_ARRAY
import numpy as np
from funcs import *

class OffscreenPanda(ShowBase):
    def __init__(self, W, H):
        super().__init__()
        self.W, self.H = W, H
        # How many iterations of thermo info to be stored before deleting old ones
        self.info_size = 300
        self.input_file = "../inputs/tersoff.in"

        # Offscreen buffer & texture
        buf = self.win.make_texture_buffer("buf", W, H, to_ram=True)
        self.tex = buf.get_texture()
        buf.add_render_texture(self.tex, GraphicsOutput.RTMCopyRam, GraphicsOutput.RTPColor)

        # Offscreen camera
        dr = buf.get_display_region(0)
        cam2 = self.make_camera(buf)
        dr.set_camera(cam2)
        lens = PerspectiveLens()
        #lens.set_fov(90)
        cam2.node().set_lens(lens)
        cam2.set_pos(4, -25, 3)
        self.cam2 = cam2
        self.cam_h = cam2.get_h()
        self.cam_p = cam2.get_p()

        self.lmp = lammps()
        self.setupLammps()

        # animTime determines how long each animation step takes
        self.animTime = 1 / 60


        # Build scene
        self.render.set_shader_auto()

        amb = AmbientLight("amb"); amb.set_color(Vec4(0.7,0.7,0.7,1))
        self.render.set_light(self.render.attach_new_node(amb))
        dlight = DirectionalLight("dir"); dlight.set_color(Vec4(1,1,1,1))
        dnp = self.render.attach_new_node(dlight); dnp.set_hpr(45,-45,0)
        self.render.set_light(dnp)

        # Simulation box
        self.boxPath = 0

        # Spin state
        self.paused = False
        self._prev  = self.taskMgr.globalClock.get_frame_time()

    def setupLammps(self):
        # Create lammps object and get initial coords
        print("Creating lammps instance...")
        self.lmp.file(self.input_file)
        self.x = self.lmp.numpy.extract_atom("x")
        self.ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.cell = np.zeros((3, 3))
        self.timestep = 1
        self.tStart = 1
        self.tStop = 1
        self.pStart = 0
        self.pStop = 0

        # Grab desired variables from read_from_file.in file
        with open(self.input_file, "r") as f:
            keywords = []
            bad_keywords = ["thermo_style", "custom"]
            lines = f.readlines()
            keyword_lines = [line for line in lines if line.rstrip().startswith("thermo_style")]
            for line in keyword_lines:
                temp = line.split(" ")
                for word in temp:
                    keywords.append(word.strip())
            for keyword in bad_keywords:
                if keyword in keywords:
                    keywords.remove(keyword)
            # Remove duplicates by turning keywords into a set (that doesn't allow for duplicates) and then back to a list
            keywords = list(set(keywords))
        # Turn keywords items into a dictionary
        self.sim_info = {}
        for keyword in keywords:
            self.sim_info[keyword.upper()] = []

        # Setup atoms
        self.atom_count = self.lmp.get_natoms()
        self.atoms = []
        self.atom_ids = self.lmp.numpy.extract_atom("id")
        # Add templates for different atoms. Add more or change values depending on amount of atoms in simulation
        self.atom_types = {1: {"color": [0.9, 0.9, 0.9], "scale": [0.1, 0.1, 0.1]},
                           2: {"color": [0.0, 0.0, 0.9], "scale": [0.15, 0.15, 0.15]}}
        self.atom_type_list = self.lmp.numpy.extract_atom("type")
        self.createAtomsTask()


    def createAtomsTask(self):
        print("Creating atoms...")
        for atom_id in self.atom_ids:
            # Load atom model. If simulation has a lot of atoms or needs to run very quickly
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


    def drawSimulationBoxTask(self):
        print("Drawing simulation box...")
        if self.boxPath != 0:
            self.boxPath.removeNode()
        self.lines = LineSegs()

        # bottom face
        p = np.zeros(3)
        self.lines.moveTo(p[0], p[1], p[2])
        for i in [1, 2, -1, -2]: # 1==x, 2==y, 3==z
            p += np.sign(i) * self.cell[abs(i)-1,:]
            self.lines.drawTo(p[0], p[1], p[2])

        # support sides
        for b in [[], [0], [1], [0,1]]: # base point cell vector combinations
            p = np.zeros(3)
            for v in b:
                p += self.cell[v, :]

            self.lines.moveTo(p[0], p[1], p[2])
            p += self.cell[2, :]
            self.lines.drawTo(p[0], p[1], p[2])

        # top face
        p = self.cell[2,:]
        self.lines.moveTo(p[0], p[1], p[2])
        for i in [1, 2, -1, -2]: # 1==x, 2==y, 3==z
            p += np.sign(i) * self.cell[abs(i)-1,:]
            self.lines.drawTo(p[0], p[1], p[2])

        self.lines.setThickness(4)
        node = self.lines.create()
        self.boxPath = NodePath(node)
        self.boxPath.reparentTo(render)

        return Task.done


    def moveAtomsTask(self):
        print("Moving atoms...")
        if not self.paused:
            starttime = time.monotonic()
            self.run_single()
            for i in range(self.atom_count):
                new_pos = (self.ix[i,:]-self.ix_old[i,:]) @ self.cell + self.x[i,:]
                self.atoms[i].setPos(new_pos[0], new_pos[1], new_pos[2])
        return Task.done


    def run_single(self):
        print("Running single...")
        # store old values for reference
        self.x_old = self.x.copy()
        self.ix_old = self.ix.copy()
        self.xu_old = self.xu.copy()

        # Run single timestep and get ids and coords of atoms
        self.lmp.command(f"run {self.timestep:.0f}")

        # Store thermo info for graphing
        extractThermo(self)

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


    def rotate_camera(self, dx, dy):
        """Called from mouse drag to orbit the offscreen camera."""
        self.cam_h = (self.cam_h - dx*0.2) % 360
        self.cam_p = max(-85, min(85, self.cam_p + dy*0.2))
        self.cam2.set_hpr(self.cam_h, self.cam_p, 0)


    def zoom_camera(self, delta):
        """Zoom in/out by moving the camera along its Y-axis."""
        cam = self.cam2
        y = cam.get_y()
        y = max(-50, min(-2, y + delta * 0.2))  # clamp between -50 and -2
        cam.set_y(y)


    def render_frame_to_qimage(self):
        # 1) Advance spin
        now = self.taskMgr.globalClock.get_frame_time()
        dt  = now - self._prev
        self._prev = now

        # 2) Render & extract
        self.graphicsEngine.render_frame()
        self.graphicsEngine.extract_texture_data(self.tex, self.win.get_gsg())

        # 3) Grab bytes and wrap in QImage
        ram = self.tex.get_ram_image()
        raw = ram.get_data()   # RGBA8
        bpl = 4 * self.W
        img = QtGui.QImage(raw, self.W, self.H, bpl, QtGui.QImage.Format.Format_RGBA8888)
        return img.mirrored(False, True)