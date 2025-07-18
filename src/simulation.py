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

# Offscreen Panda3D config
load_prc_file_data("", "window-type offscreen")
load_prc_file_data("", "gl-force-software true")

class OffscreenPanda(ShowBase):
    def __init__(self, W, H):
        super().__init__()
        self.W, self.H = W, H

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

        # Create lammps object and get initial coords
        self.lmp = lammps()
        self.lmp.file("../inputs/read_from_file.in")
        self.x = self.lmp.numpy.extract_atom("x")
        self.ix = self.lmp.numpy.extract_compute("compute_ix", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.xu = self.lmp.numpy.extract_compute("compute_xu", LMP_STYLE_ATOM, LMP_TYPE_ARRAY)
        self.cell = np.zeros((3, 3))
        self.timestep = 1
        self.tStart = 1
        self.tStop = 1
        # How many iterations of thermo info to be stored before deleting old ones
        self.info_size = 1000
        self.sim_info = {"Step": [], "v_diffusion_coeff_light": [], "v_msd_light": [], "v_diffusion_coeff_heavy": [],
                         "v_msd_heavy": [], "Temp": [], "Press": []}
        self.graphs = {"Temp": 0, "Press": 0}

        self.atom_count = self.lmp.get_natoms()
        self.atoms = []
        self.atom_ids = self.lmp.numpy.extract_atom("id")

        # animTime determines how long each animation step takes
        self.animTime = 1 / 60

        # Add templates for different atoms. Add more or change values depending on amount of atoms in simulation
        self.atom_types = {1: {"color": [0.9, 0.9, 0.9], "scale": [0.1, 0.1, 0.1]},
                           2: {"color": [0.0, 0.0, 0.9], "scale": [0.15, 0.15, 0.15]}}
        self.atom_type_list = self.lmp.numpy.extract_atom("type")

        # Build scene
        self.render.set_shader_auto()

        amb = AmbientLight("amb"); amb.set_color(Vec4(0.7,0.7,0.7,1))
        self.render.set_light(self.render.attach_new_node(amb))
        dlight = DirectionalLight("dir"); dlight.set_color(Vec4(1,1,1,1))
        dnp = self.render.attach_new_node(dlight); dnp.set_hpr(45,-45,0)
        self.render.set_light(dnp)

        # Spin state
        self.paused = False
        self._prev  = self.taskMgr.globalClock.get_frame_time()


    def createAtomsTask(self):
        print("Creating atoms...")
        for atom_id in self.atom_ids:
            # Load atom model. If simulation has a lot of atoms or needs to run very quickly,l
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


    def moveAtomsTask(self):
        print("Moving atoms...")
        if not panda.paused:
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


class PandaLabel(QtWidgets.QLabel):
    """A QLabel that forwards left-drag deltas to OffscreenPanda.rotate_camera."""
    def __init__(self, panda: OffscreenPanda, parent=None):
        super().__init__(parent)
        self.panda = panda
        self.setMouseTracking(True)
        self._last = None


    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        if ev.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._last = ev.position()


    def mouseMoveEvent(self, ev: QtGui.QMouseEvent):
        if self._last and (ev.buttons() & QtCore.Qt.MouseButton.LeftButton):
            curr = ev.position()
            dx = curr.x() - self._last.x()
            dy = curr.y() - self._last.y()
            self.panda.rotate_camera(dx, dy)
            self._last = curr


    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent):
        self._last = None


    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y() / 120  # 1 unit per notch
        self.panda.zoom_camera(delta)  # negative to zoom in on scroll up


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, panda: OffscreenPanda):
        super().__init__()
        self.panda = panda
        self.setWindowTitle("Interactive Panda3D + PyQt6")

        # Layouts
        central = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout(central)

        # Sidebar
        sidebar = QtWidgets.QWidget()
        sidebar.setMinimumWidth(500)
        vbox = QtWidgets.QVBoxLayout(sidebar)
        self.btn = QtWidgets.QPushButton("Pause")
        self.btn.clicked.connect(self.toggle_play)
        vbox.addWidget(self.btn)
        vbox.addWidget(QtWidgets.QLabel("Simulation Speed:"))
        self.sld = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.sld.setRange(1, 10)
        self.sld.valueChanged.connect(lambda v: changeSpeed(panda, v))
        vbox.addWidget(self.sld)
        vbox.addWidget(QtWidgets.QLabel("Thermostat:"))
        self.sld = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.sld.setRange(-5, 5)
        self.sld.valueChanged.connect(lambda v: changeThermo(panda, v))
        vbox.addWidget(self.sld)
        self.graph = pg.PlotWidget(title="Temperature over Time")
        self.graph.setLabel('left','Temperature')
        self.graph.setLabel('bottom','Time','s')
        self.curve = self.graph.plot(pen='y')
        self.xdata, self.ydata = [], []
        self.start = time.time()
        vbox.addWidget(self.graph)
        vbox.addStretch(1)

        # Panda image label
        self.label = PandaLabel(panda)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(panda.W, panda.H)

        # Assemble
        hbox.addWidget(sidebar)
        hbox.addWidget(self.label, 1)
        self.setCentralWidget(central)
        self.resize(panda.W + 250, panda.H)

        # Frame timer
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.update_frame)
        timer.start(33)


    @QtCore.pyqtSlot()
    def update_frame(self):
        if not self.panda.paused:
            # Run a simulation step
            panda.moveAtomsTask()
            # Draw Panda frame
            qimg = self.panda.render_frame_to_qimage()
            self.label.setPixmap(QtGui.QPixmap.fromImage(qimg))
            # Update graph
            t = time.time() - self.start
            extractThermo(panda)
            self.xdata, self.ydata = panda.sim_info["Step"], panda.sim_info["Temp"]
            if len(self.xdata) > 300:
                self.xdata.pop(0); self.ydata.pop(0)
            self.curve.setData(self.xdata, self.ydata)


    def toggle_play(self):
        self.panda.paused = not self.panda.paused
        self.btn.setText("Play" if self.panda.paused else "Pause")


if __name__ == "__main__":
    W, H = 960, 720
    panda = OffscreenPanda(W, H)
    panda.createAtomsTask()
    panda.moveAtomsTask()
    panda.drawSimulationBoxTask()

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(panda)
    win.show()
    sys.exit(app.exec())