from threading import Thread
from typing import Optional

from PyQt5.QtWidgets import QWidget


def background(func):
    def wrapper(cl, *args, **kwargs):
        if cl._thread and cl._thread.is_alive():
            return
        cl._thread = Thread(target=cl._background, args=(func, *args), kwargs=kwargs)
        cl._thread.start()

    return wrapper


class ComponentTab(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        if kwargs.get("refreshers"):
            self._refreshers = kwargs["refreshers"]
        else:
            self._refreshers = []
        self._thread: Optional[Thread] = None

    def refresh(self):
        for refr in self._refreshers:
            refr.refresh()

    def _background(self, _background_process, *args, **kwargs):
        for ch in self.findChildren():
            ch.setEnabled(False)
        _background_process(*args, **kwargs)
        for ch in self.findChildren():
            ch.setEnabled(True)
