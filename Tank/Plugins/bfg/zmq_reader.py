import zmq
import logging
import json

class ZmqReader(object):

    '''Read missiles from zmq'''

    def __init__(self):
        self.queue = "tcp://127.0.0.1:43000" #queue
        self.log = logging.getLogger(__name__)
        context = zmq.Context()
        self.socket = context.socket(zmq.PULL)
        self.socket.connect(self.queue)
        self.log.info("ZMQ: Waiting for missiles from '%s'" % self.queue)

    def __iter__(self):
        while True:
          try:
              data = self.socket.recv()
              yield(tuple(json.loads(data)))
          except Exception as e:
              print(e)
