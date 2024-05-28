from ..common.interfaces import AbstractMetric, TypeTimeSeries, TypeQuantiles, TypeDistribution
import numpy as np


class Metric(AbstractMetric):
    def __init__(self, **kw):
        super(Metric, self).__init__(**kw)
        self.dtypes = {
            'ts': np.int64,
            'value': np.float64
        }
        self.columns = ['ts', 'value']

    @property
    def type(self):
        return TypeTimeSeries

    @property
    def aggregate_types(self):
        return [TypeQuantiles, TypeDistribution]
