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
from timeit import default_timer as timer

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, panda: OffscreenPanda):
        super().__init__()
        self.panda = panda
        self.setWindowTitle("LAMMPS simulation")
        self.graphs = {}
        self.curves = {}
        self.graph_min_size = [300, 200]    #Height, Width
        self.total_cycle_time = 0
        self.cycle_count = 0

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

        # Show object toggle buttons
        show_buttonbox = QtWidgets.QHBoxLayout()
        vbox.addLayout(show_buttonbox)
        self.showboxbtn = QtWidgets.QPushButton("Box: Hide")
        self.showboxbtn.clicked.connect(lambda: self.toggle_show_object("box"))
        show_buttonbox.addWidget(self.showboxbtn)
        self.showatomsbtn = QtWidgets.QPushButton("Atoms: Hide")
        self.showatomsbtn.clicked.connect(lambda: self.toggle_show_object("atoms"))
        show_buttonbox.addWidget(self.showatomsbtn)
        self.showbondsbtn = QtWidgets.QPushButton("Bonds: Hide")
        self.showbondsbtn.clicked.connect(lambda: self.toggle_show_object("bonds"))
        show_buttonbox.addWidget(self.showbondsbtn)

        self.simSpeedLabel = QtWidgets.QLabel(f"Simulation Speed: {panda.timestep}")
        vbox.addWidget(self.simSpeedLabel)
        self.speedSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speedSlider.setRange(1, 10)
        self.speedSlider.valueChanged.connect(lambda v: changeSpeed(panda, self.simSpeedLabel, v))
        vbox.addWidget(self.speedSlider)

        self.tempSliderLabel = QtWidgets.QLabel(f"Thermostat: {panda.tStop}")
        vbox.addWidget(self.tempSliderLabel)
        self.tempSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
#        self.tempSlider.setRange(-5000, 13000) # migudo
        self.tempSlider.setRange(0, 20000) # migudo
        self.tempSlider.valueChanged.connect(lambda v: changeThermo(panda, self.tempSliderLabel, v))
        self.tempSlider.setTickInterval(1000)
        self.tempSlider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)
        vbox.addWidget(self.tempSlider)

        self.pressSliderLabel = QtWidgets.QLabel(f"Barostat: {panda.pStop}")
        vbox.addWidget(self.pressSliderLabel)
        self.pressSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
#        self.pressSlider.setRange(-1000, 1000) # migudo
        self.pressSlider.setRange(0, 1000000) # migudo
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
                             "TEMP": {"ignore": False, "title": "Temperature over Time", "x-unit": "dt", "y-unit": "K","y-label": "Temperature", "x-label": "Time", "x-var": "Step"},
                             "PRESS": {"ignore": False, "title": "Pressure over Time",  "x-unit": "dt", "y-unit": "bar", "y-label": "Pressure", "x-label": "Time", "x-var": "Step"},
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

    def toggle_show_object(self, object):
        if object == "box":
            if self.panda.show_box:
                self.panda.box_path.hide()
                self.showboxbtn.setText("Box: Show")
            else:
                self.panda.box_path.show()
                self.showboxbtn.setText("Box: Hide")
            self.panda.show_box = not self.panda.show_box
        if object == "atoms":
            if self.panda.show_atoms:
                for i in range(len(self.panda.atoms)):
                    self.panda.atoms[i].hide()
                    self.showatomsbtn.setText("Atoms: Show")
            else:
                for i in range(len(self.panda.atoms)):
                    self.panda.atoms[i].show()
                    self.showatomsbtn.setText("Atoms: Hide")
            self.panda.show_atoms = not self.panda.show_atoms
        if object == "bonds":
            if self.panda.show_bonds:
                self.panda.bond_node.hide()
                self.showbondsbtn.setText("Bonds: Show")
            else:
                self.panda.bond_node.show()
                self.showbondsbtn.setText("Bonds: Hide")
            self.panda.show_bonds = not self.panda.show_bonds

    @QtCore.pyqtSlot()
    def update_frame(self):
        if not self.panda.paused:
            # Run a simulation step
            move_start = timer()
            self.panda.moveAtomsTask()
            move_end = timer()
            print(f"Moved atoms in {move_end - move_start} seconds")
            # Draw Panda frame
            panda_frame_start = timer()
            qimg = self.panda.render_frame_to_qimage()
            self.label.setPixmap(QtGui.QPixmap.fromImage(qimg))
            panda_frame_end = timer()
            print(f"Drew panda label in {panda_frame_end - panda_frame_start} seconds")
            # Update graphs
            graph_start = timer()
            extractThermo(self.panda)
            for key in self.graphs:
                self.xdata, self.ydatas[key] = self.panda.sim_info["STEP"], self.panda.sim_info[key]
                self.curves[key].setData(self.xdata, self.ydatas[key])
            if len(self.xdata) > self.panda.info_size:
                self.xdata.pop(0)
                for key in self.ydatas:
                    self.ydatas[key].pop(0)
            graph_end = timer()
            print(f"Updated graphs in {graph_end - graph_start} seconds")
            # Draw simulation box
            box_start = timer()
            if self.panda.show_box:
                self.panda.drawSimulationBoxTask()
            box_end = timer()
            print(f"Drew simulation box in {box_end - box_start} seconds")
            # Draw bonds
            bonds_start = timer()
            if self.panda.show_bonds:
                self.panda.drawBondsTask()
            bonds_end = timer()
            print(f"Drew bonds in {bonds_end - bonds_start} seconds")
            cycle_time = move_end - move_start + panda_frame_end - panda_frame_start + graph_end - graph_start + box_end - box_start + bonds_end - bonds_start
            self.total_cycle_time += cycle_time
            self.cycle_count += 1
            average_cycle_time = self.total_cycle_time / self.cycle_count
            print(f"Total runtime: {cycle_time} seconds")
            print(f"Average cycle time: {average_cycle_time} seconds")
