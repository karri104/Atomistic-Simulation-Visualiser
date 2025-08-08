import sys, time
from PyQt6 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from PyQt6.QtWidgets import QGroupBox
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
from pandalabel import PandaLabel
from panda import OffscreenPanda

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, panda: OffscreenPanda):
        super().__init__()
        self.panda = panda
        self.setWindowTitle("LAMMPS simulation")
        self.graphs = {}
        self.curves = {}
        self.graph_min_size = [300, 200]    #Height, Width

        # Layouts
        central = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout(central)

        # Sidebar
        sidebar = QtWidgets.QWidget()
        sidebar.setMinimumWidth(500)
        vbox = QtWidgets.QVBoxLayout(sidebar)

        # Pause & Reset buttons
        buttonbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(buttonbox)
        self.startstopbtn = QtWidgets.QPushButton("Pause")
        self.startstopbtn.clicked.connect(self.toggle_play)
        buttonbox.addWidget(self.startstopbtn)
        self.resetbtn = QtWidgets.QPushButton("Reset")
        self.resetbtn.clicked.connect(self.reset_simulation)
        buttonbox.addWidget(self.resetbtn)

        self.simSpeedLabel = QtWidgets.QLabel(f"Simulation Speed: {panda.timestep}")
        vbox.addWidget(self.simSpeedLabel)
        self.speedSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speedSlider.setRange(1, 10)
        self.speedSlider.valueChanged.connect(lambda v: changeSpeed(panda, self.simSpeedLabel, v))
        vbox.addWidget(self.speedSlider)

        self.tempSliderLabel = QtWidgets.QLabel(f"Thermostat: {panda.tStop}")
        vbox.addWidget(self.tempSliderLabel)
        self.tempSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.tempSlider.setRange(-5000, 15000)
        self.tempSlider.valueChanged.connect(lambda v: changeThermo(panda, self.tempSliderLabel, v))
        self.tempSlider.setTickInterval(1000)
        self.tempSlider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        vbox.addWidget(self.tempSlider)

        self.pressSliderLabel = QtWidgets.QLabel(f"Barostat: {panda.pStop}")
        vbox.addWidget(self.pressSliderLabel)
        self.pressSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.pressSlider.setRange(-1000, 1000)
        self.pressSlider.valueChanged.connect(lambda v: changeBaro(panda, self.pressSliderLabel, v))
        vbox.addWidget(self.pressSlider)

        # Create a box for toggling individual graphs
        buttonHBox = QtWidgets.QHBoxLayout()
        self.graphGraphicalBox = QtWidgets.QGroupBox("Graph Toggles")
        vbox.addWidget(self.graphGraphicalBox)
        self.graphCheckboxes = {}
        for key in self.panda.sim_info.keys():
            if key != "STEP":
                checkbox = QtWidgets.QCheckBox(key)
                checkbox.stateChanged.connect(lambda state, name=key: toggleGraphView(self, name, state))
                self.graphCheckboxes[key] = checkbox
                buttonHBox.addWidget(checkbox)
        self.graphGraphicalBox.setLayout(buttonHBox)
        vbox.addWidget(self.graphGraphicalBox)


        # Graphing stuff. Creates a box with checkboxes for each "graphable" variable which toggles graph drawing for
        # said variables. Note: data collection for these variables always happens regardless of these checkboxes
        print("Creating graphs...")
        # This key_format dictionary determines graphing options for default behaviour and special cases (mainly just units)
        var_name = ""
        self.special_keys = {"STEP": {"ignore": True, "title": "", "unit": "", "y-label": "", "x-label": ""},
                             "TEMP": {"ignore": False, "title": "Temperature over Time", "x-unit": "dt", "y-unit": "","y-label": "Temperature", "x-label": "Time", "x-var": "Step"},
                             "PRESS": {"ignore": False, "title": "Pressure over Time",  "x-unit": "dt", "y-unit": "", "y-label": "Pressure", "x-label": "Time", "x-var": "Step"},
                             "DEFAULT": {"ignore": False, "title": " over Time",  "x-unit": "dt", "y-unit": "", "y-label": "", "x-label": "Time", "x-var": "Step"}}
        for key in self.panda.sim_info.keys():
            if key in self.special_keys:
                if self.special_keys[key]["ignore"] != True:
                    self.graph = pg.PlotWidget(title=self.special_keys[key]["title"])
                    self.graph.setLabel("left", self.special_keys[key]["y-label"], self.special_keys[key]["y-unit"])
                    self.graph.setLabel("bottom", self.special_keys[key]["x-label"], self.special_keys[key]["x-unit"])
                    self.curve = self.graph.plot(pen='y')
                    self.xdata, self.ydatas = [], {}
                    self.start = time.time()
                    self.graph.setMinimumSize(self.graph_min_size[0], self.graph_min_size[1])
                    self.graph.resize(self.graph_min_size[0], self.graph_min_size[1])
                    vbox.addWidget(self.graph)
                    vbox.addStretch(1)
                    self.graphs[key] = self.graph
                    self.curves[key] = self.curve
            else:
                var_name = key
                key = "DEFAULT"
                if self.special_keys[key]["ignore"] != True:
                    self.graph = pg.PlotWidget(title=var_name + self.special_keys[key]["title"])
                    self.graph.setLabel("left", var_name + self.special_keys[key]["y-label"], self.special_keys[key]["y-unit"])
                    self.graph.setLabel("bottom", self.special_keys[key]["x-label"], self.special_keys[key]["x-unit"])
                    self.curve = self.graph.plot(pen='y')
                    self.xdata, self.ydatas = [], {}
                    self.start = time.time()
                    self.graph.setMinimumSize(self.graph_min_size[0], self.graph_min_size[1])
                    self.graph.resize(self.graph_min_size[0], self.graph_min_size[1])
                    vbox.addWidget(self.graph)
                    vbox.addStretch(1)
                    self.graphs[var_name] = self.graph
                    self.curves[var_name] = self.curve

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

    def toggle_play(self):
        self.panda.paused = not self.panda.paused
        self.startstopbtn.setText("Play" if self.panda.paused else "Pause")

    def reset_simulation(self):
        print("Resetting simulation...")
        for atom in self.panda.atoms:
            atom.removeNode()
        self.speedSlider.setValue(1)
        self.tempSlider.setValue(1)
        self.pressSlider.setValue(0)
        self.panda.lmp.command(f"clear")
        self.panda.setupLammps()

    @QtCore.pyqtSlot()
    def update_frame(self):
        if not self.panda.paused:
            # Run a simulation step
            self.panda.moveAtomsTask()
            # Draw Panda frame
            qimg = self.panda.render_frame_to_qimage()
            self.label.setPixmap(QtGui.QPixmap.fromImage(qimg))
            # Update graphs
            t = time.time() - self.start
            extractThermo(self.panda)
            for key in self.graphs:
                self.xdata, self.ydatas[key] = self.panda.sim_info["STEP"], self.panda.sim_info[key]
                self.curves[key].setData(self.xdata, self.ydatas[key])
            if len(self.xdata) > self.panda.info_size:
                self.xdata.pop(0)
                for key in self.ydatas:
                    self.ydatas[key].pop(0)
            self.panda.drawSimulationBoxTask()