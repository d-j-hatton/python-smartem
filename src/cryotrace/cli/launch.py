from cryotrace.data_model.extract import DataAPI
from cryotrace.gui.qt import App


def run():
    extractor = DataAPI()
    app = App(extractor)
    app.start()
