import sys
from PyQt6 import QtWidgets
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.gui.DirectGui import *
from panda3d.core import *
from lammps import lammps, LMP_TYPE_VECTOR, LMP_STYLE_ATOM, LMP_TYPE_ARRAY
from panda import OffscreenPanda
from mainwindow import MainWindow

# Offscreen Panda3D config
load_prc_file_data("", "window-type offscreen")
load_prc_file_data("", "gl-force-software true")


if __name__ == "__main__":
    W, H = 1080, 960
    panda = OffscreenPanda(W, H)
    panda.moveAtomsTask()
    panda.drawSimulationBoxTask()

    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow(panda)
    win.show()
    sys.exit(app.exec())