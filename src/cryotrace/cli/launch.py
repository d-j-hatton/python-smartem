from cryotrace.data_model.extract import Extractor
from cryotrace.gui.qt import App


def run():
    extractor = Extractor()
    app = App(extractor)
    app.start()
