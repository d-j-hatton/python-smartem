from smartem.data_model.extract import DataAPI
from smartem.gui.qt import App


def run():
    extractor = DataAPI()
    app = App(extractor)
    app.start()
