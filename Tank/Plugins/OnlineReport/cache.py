from collections import defaultdict
import json


def collect_subtree(storage, subtree, ts):
    for key, node in subtree.iteritems():
        if type(node) is not dict:
            storage.setdefault(key, []).append((ts, node))
        else:
            collect_subtree(storage.setdefault(key, {}), node, ts)


class DataCacher(object):

    def __init__(self):
        self.storage = {}

    def store(self, data):
        for ts, subtree in data.iteritems():
            collect_subtree(self.storage, subtree, ts)
