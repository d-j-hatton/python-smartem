from PyQt5.QtWidgets import QWidget


class ComponentTab(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()
        if kwargs.get("refreshers"):
            self._refreshers = kwargs["refreshers"]
        else:
            self._refreshers = []

    def refresh(self):
        for refr in self._refreshers:
            refr.refresh()
