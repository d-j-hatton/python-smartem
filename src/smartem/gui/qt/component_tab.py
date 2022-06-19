from multiprocessing import Process, Queue
from threading import Thread
from typing import List, NamedTuple, Optional, Type

from PyQt5.QtWidgets import QWidget


class MethodRequest(NamedTuple):
    method: str
    args: tuple
    kwargs: dict


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


class TabWrapper:
    def __init__(self, comp_tab_type: Type[ComponentTab], *args, **kwargs):
        self._comp_tab_type = comp_tab_type
        self._process = Process(target=self._process_loop, args=args, kwargs=kwargs)
        self._queue: Queue = Queue()
        self._process.start()

    def _process_loop(self, *args, **kwargs):
        comp_tab = self._comp_tab_type(*args, **kwargs)
        while method_request := self._queue.get():
            if not isinstance(method_request, MethodRequest):
                raise ValueError(
                    f"Incorrect form passed to TabWrapper process loop: {method_request}"
                )
            getattr(comp_tab, method_request.method)(
                *method_request.args, **method_request.kwargs
            )

    def _tab_call(self, method_name: str, *args, **kwargs):
        self._queue.put(MethodRequest(method_name, args, kwargs))

    def refresh(self):
        self._tab_call("refresh")
