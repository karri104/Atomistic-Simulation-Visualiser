import math
import numpy as np
from PyQt6 import QtGui
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.DirectGui import *
from panda3d.core import *
from lammps import lammps, LMP_TYPE_VECTOR, LMP_STYLE_ATOM, LMP_TYPE_ARRAY
from ase import Atoms
from ase.neighborlist import NeighborList
from funcs import *
import os

class OffscreenPanda(ShowBase):
    def __init__(self, W, H):
        super().__init__()
        self.W, self.H = W, H
        # How many iterations of thermo info to be stored before deleting old ones
        self.info_size = 300
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_file = os.path.join(base_dir, '../inputs/tersoff.in')
        self.cutoffs = []
        self.max_cutoff = 0
        self.bond_pairs = []
        self.bond_geom_node = 0
        self.bond_node = 0

        # Offscreen buffer & texture
        buf = self.win.make_texture_buffer("buf", W, H, to_ram=True)
        self.tex = buf.get_texture()
        buf.add_render_texture(self.tex, GraphicsOutput.RTMCopyRam, GraphicsOutput.RTPColor)

        # Offscreen camera
        dr = buf.get_display_region(0)
        cam2 = self.make_camera(buf)
        dr.set_camera(cam2)
        lens = PerspectiveLens()
        self.cam_fov = 45 # vertical fov of camera
        lens.set_fov(self.cam_fov)
        cam2.node().set_lens(lens)
        cam2.set_pos(4, -25, 3)
        self.cam2 = cam2
        self.cam_h = cam2.get_h()
        self.cam_p = cam2.get_p()

        self.lmp = lammps(cmdargs=["-log", "none", "-screen", "none", "-nocite"])
        self.setupLammps()

        # Build scene
        self.render.set_shader_auto()

        amb = AmbientLight("amb"); amb.set_color(Vec4(0.7,0.7,0.7,1))
        self.render.set_light(self.render.attach_new_node(amb))
        dlight = DirectionalLight("dir"); dlight.set_color(Vec4(1,1,1,1))
        dnp = self.render.attach_new_node(dlight); dnp.set_hpr(45,-45,0)
        self.render.set_light(dnp)

        # Simulation box
        self.box_path = 0
        self.vertices = []

        # Flags
        self.paused = False
        self._prev  = self.taskMgr.globalClock.get_frame_time()
        self.cutoff_cached = False
        self.show_box = True
        self.show_atoms = True
        self.show_bonds = True

        # Create a pivot node (the point you want to orbit around)
        self.cam_pivot = self.render.attach_new_node("cam_pivot")
        self.cam_pivot.set_pos(10, 10, 10)

        # Reparent the camera to the pivot
        self.cam2.reparent_to(self.cam_pivot)

        # Set initial distance from pivot
        self.cam_distance = 60
        self.cam2.set_pos(0, -self.cam_distance, 3)

    def setupLammps(self):
        # Create lammps object and get initial coords
        print("Creating lammps instance...")
        self.lmp.file(self.input_file)
        self.atom_ids = self.lmp.numpy.extract_atom("id")
        self.x = self.lmp.numpy.extract_atom("x")[0:len(self.atom_ids)]
        self.ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.cell = np.zeros((3, 3))
        self.timestep = 1
        self.tStart = 1
        self.tStop = 1
        self.pStart = 0
        self.pStop = 0
        self.bond_pairs = []
        self.vertices = []

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
        self.type_to_symbol = {1: "C"}
        # Add templates for different atoms. Add more or change values depending on amount of atoms in simulation
        self.atom_types = {"C": {"color": [0.1, 0.1, 0.1, 1], "scale": [0.2, 0.2, 0.2]},
                           2: {"color": [0.0, 0.0, 0.9, 1], "scale": [0.15, 0.15, 0.15]}}
        self.atom_bond_cutoffs = {"C": 1.85}
        self.atom_type_list = self.lmp.numpy.extract_atom("type")[0:len(self.atom_ids)]
        self.atom_symbols = [self.type_to_symbol[t] for t in self.atom_type_list]
        self.createAtomsTask()

    def createAtomsTask(self):
        print("Creating atoms...")
        for atom_id in self.atom_ids:
            # Load atom model. If simulation has a lot of atoms or needs to run very quickly
            # change the model to a lower poly version, which can be found online. Any .egg file should work.
            atom = self.loader.loadModel('../models/Sphere.egg')
            # Reparent to render (important to do this so the model can be rendered)'
            atom.reparentTo(self.render)
            if self.atom_symbols[atom_id - 1] in self.atom_types.keys():
                atom.setColor(self.atom_types[self.atom_symbols[atom_id - 1]]["color"][0],
                              self.atom_types[self.atom_symbols[atom_id - 1]]["color"][1],
                              self.atom_types[self.atom_symbols[atom_id - 1]]["color"][2], 1)
                atom.setScale(self.atom_types[self.atom_symbols[atom_id - 1]]["scale"][0],
                              self.atom_types[self.atom_symbols[atom_id - 1]]["scale"][1],
                              self.atom_types[self.atom_symbols[atom_id - 1]]["scale"][2])
            # Give atoms random positions
            atom.setPos(self.x[atom_id - 1][0], self.x[atom_id - 1][1], self.x[atom_id - 1][2])
            # Add atoms to a list, so they can be easily accessed later
            self.atoms.append(atom)
        return Task.done

    def drawSimulationBoxTask(self):
        # print("Drawing simulation box...")
        if self.box_path != 0:
            self.box_path.removeNode()
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
        self.box_path = NodePath(node)
        self.box_path.reparentTo(render)

        return Task.done

    def drawBondsTask(self):
        # print("Drawing bonds...")
        calcAtomPairs(self)
        create_bond_geometry(self)
        return Task.done


    def moveAtomsTask(self):
        # print("Moving atoms...")
        if not self.paused:
            self.run_single()
            for i in range(self.atom_count):
                self.atoms[i].setPos(self.x[i][0], self.x[i][1], self.x[i][2])
        return Task.done


    def center_camera(self):
        # Return a list of (x, y, z) vertices from a LineSegs-created Geom
        geom_node = self.box_path.node()
        for i in range(geom_node.get_num_geoms()):
            geom = geom_node.get_geom(i)
            vdata = geom.get_vertex_data()
            reader = GeomVertexReader(vdata, "vertex")
        while not reader.is_at_end():
            x = reader.get_data3f()
            x_data = [x[0], x[1], x[2]]
            self.vertices.append(x_data)

        # Find max distance between vertices to find needed camera position
        vertices = np.array(self.vertices)
        # Geometric center of box
        center = vertices.mean(axis=0)
        # Find farthest vertex from center
        distances = np.linalg.norm(vertices - center, axis=1)
        radius = distances.max()
        # Camera distance
        self.cam_distance = radius / math.sin(math.radians(self.cam_fov/2))
        self.cam2.set_y(-self.cam_distance)
        self.cam_pivot.set_pos(center[0], center[1], center[2])


    def run_single(self):
        # print("Running single...")
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

        atom_ids = self.lmp.numpy.extract_atom("id")[0:len(self.atom_ids)] # migudo
        x = self.lmp.numpy.extract_atom("x")
        ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)

        x_sorted = np.zeros(x.shape)
        ix_sorted = np.zeros(ix.shape)
        xu_sorted = np.zeros(xu.shape)
        # TODO: Remove loop (use numpy array methods)
        for i in range(len(atom_ids)):
            x = self.lmp.numpy.extract_atom("x")[0:len(self.atom_ids)] # migudo
            ix_sorted[atom_ids[i]-1, :] = ix[i, :]
            xu_sorted[atom_ids[i]-1, :] = xu[i, :]
        self.x = x
        self.ix = ix_sorted

    def rotate_camera(self, dx, dy):
        # Update heading/pitch of pivot
        h = self.cam_pivot.get_h() - dx * 0.2
        p = self.cam_pivot.get_p() + dy * 0.2
        p = max(-85, min(85, p))
        self.cam_pivot.set_hpr(h, p, 0)

    def zoom_camera(self, delta):
        # Zoom by changing distance from pivot
        self.cam_distance = self.cam_distance - delta
        self.cam2.set_y(-self.cam_distance)

    def pan_camera(self, dx, dy):
        # Pan the pivot in camera space (middle mouse drag).
        # Sensitivity
        speed = 0.002 * self.cam_distance  # scale with zoom level
        # Convert pixel delta to movement in camera space
        # dx -> move right, dy -> move up
        right = self.cam2.get_quat().get_right()
        up = self.cam2.get_quat().get_up()
        move = (right * (-dx * speed)) + (up * (dy * speed))
        # Apply to pivot
        self.cam_pivot.set_pos(self.cam_pivot.get_pos() + move)

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