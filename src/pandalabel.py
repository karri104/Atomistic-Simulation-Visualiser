from PyQt6 import QtWidgets, QtCore, QtGui
from panda import OffscreenPanda


class PandaLabel(QtWidgets.QLabel):
    """A QLabel that forwards left-drag deltas to OffscreenPanda.rotate_camera."""
    def __init__(self, panda: OffscreenPanda, parent=None):
        super().__init__(parent)
        self.panda = panda
        self.setMouseTracking(True)
        self._last = None
        self._middle_last = None


    def mousePressEvent(self, ev: QtGui.QMouseEvent):
        if ev.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._last = ev.position()
        if ev.buttons() & QtCore.Qt.MouseButton.MiddleButton:
            self._middle_last = ev.position()


    def mouseMoveEvent(self, ev: QtGui.QMouseEvent):
        # Orbit (left button)
        if self._last and (ev.buttons() & QtCore.Qt.MouseButton.LeftButton):
            curr = ev.position()
            dx = curr.x() - self._last.x()
            dy = curr.y() - self._last.y()
            self.panda.rotate_camera(dx, dy)
            self._last = curr
        # Pan (middle button)
        if self._middle_last and (ev.buttons() & QtCore.Qt.MouseButton.MiddleButton):
            curr = ev.position()
            dx = curr.x() - self._middle_last.x()
            dy = curr.y() - self._middle_last.y()
            self.panda.pan_camera(dx, dy)
            self._middle_last = curr


    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent):
        self._last = None
        self._middle_last = None


    def wheelEvent(self, event: QtGui.QWheelEvent):
        delta = event.angleDelta().y() / 120  # 1 unit per notch
        self.panda.zoom_camera(delta)  # negative to zoom in on scroll up

