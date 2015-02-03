import zmq
import logging
import json
import threading as th

class ZmqReader(object):

    '''Read missiles from zmq'''

    def __init__(self, queue):
        self.queue = queue
        self.quit = th.Event()
        self.log = logging.getLogger(__name__)
        context = zmq.Context()
        self.socket = context.socket(zmq.PULL)
        self.socket.connect(self.queue)
        self.log.info("ZMQ: Waiting for missiles from '%s'" % self.queue)

    def __iter__(self):
        while True:
          try:
              if not self.socket.poll(500):
                  if self.quit.is_set():
                      raise StopIteration()
                  continue

              data = tuple(self.socket.recv_json())

              if len(data) != 3:
                  if data[0] == "stop":
                      raise StopIteration()
                  continue

              yield(data)
          except StopIteration:
              raise
          except Exception as e:
              print(e)

    def stop(self):
        self.quit.set()
