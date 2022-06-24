import numpy as np
import plotly.graph_objects as go
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg


class InteractivePlot(FigureCanvasQTAgg):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._data: list = []

    def set_data(self, data):
        self._data = data

    def mousePressEvent(self, ev):
        axes = self.figure.get_axes()
        labels = axes[0].xaxis.label.get_text(), axes[0].yaxis.label.get_text()
        data_shape = np.array(self._data).shape
        if not data_shape:
            return
        if len(data_shape) == 1:
            fig = go.Figure(data=[go.Histogram(x=self._data)])
            fig.update_xaxes(title_text=labels[0])
            fig.update_yaxes(title_text=labels[1])
        elif len(data_shape) == 2:
            if data_shape[0] == 2:
                fig = go.Figure(
                    data=[go.Scatter(x=self._data[0], y=self._data[1], mode="markers")]
                )
                fig.update_xaxes(title_text=labels[0])
                fig.update_yaxes(title_text=labels[1])
            else:
                tick_labels = [tl.get_text() for tl in axes[0].xaxis.get_ticklabels()]
                fig = go.Figure(
                    data=[go.Heatmap(x=tick_labels, y=tick_labels, z=self._data)]
                )
                fig["layout"]["yaxis"]["autorange"] = "reversed"
        fig.show()
