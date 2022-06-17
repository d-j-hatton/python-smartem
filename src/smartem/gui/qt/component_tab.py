from multiprocessing import Process
from threading import Thread
from typing import List, Optional

from PyQt5.QtWidgets import QWidget


def background(
    children: Optional[List[str]] = None, lock_self: bool = False, process: bool = False
):
    if not children:
        children = []

    def background_decorator(func, *args, **kwargs):
        def wrapper(cl, *args, **kwargs):
            if cl._thread and cl._thread.is_alive():
                return
            frozen_widgets = [getattr(cl, ch) for ch in children]
            if lock_self:
                frozen_widgets.append(cl)
            if process:
                cl._thread = Process(
                    target=cl._background,
                    args=(func, *args),
                    kwargs={"_children": frozen_widgets, **kwargs},
                )
            else:
                cl._thread = Thread(
                    target=cl._background,
                    args=(func, *args),
                    kwargs={"_children": frozen_widgets, **kwargs},
                )
            cl._thread.start()

        return wrapper

    return background_decorator


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
        children = kwargs.get("_children")
        try:
            kwargs.pop("_children")
        except KeyError:
            pass
        if children is not None:
            for ch in children:
                ch.setEnabled(False)
        else:
            for ch in self.findChildren(QWidget):
                ch.setEnabled(False)
        _background_process(self, *args, **kwargs)
        if children is not None:
            for ch in children:
                ch.setEnabled(True)
        else:
            for ch in self.findChildren(QWidget):
                ch.setEnabled(True)
