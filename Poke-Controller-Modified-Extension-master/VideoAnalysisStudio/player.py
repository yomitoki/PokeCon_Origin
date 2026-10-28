"""Single decoder thread with stale-result rejection and a displayed-frame clock."""
import queue
import threading
import time

import cv2

from .detection import read_at
from .model import number, require_source


class Decoder:
    def __init__(self):
        self.requests = queue.Queue(maxsize=1)
        self.results = queue.Queue(maxsize=2)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name='VideoReviewDecoder', daemon=True)
        self.thread.start()

    def request(self, token, source, seconds, size):
        while True:
            try:
                self.requests.get_nowait()
            except queue.Empty:
                break
        self.requests.put_nowait((token, source, seconds, size))

    def _run(self):
        cap, previous = None, None
        try:
            while not self.closed.is_set():
                try:
                    token, source, seconds, size = self.requests.get(timeout=.1)
                except queue.Empty:
                    continue
                try:
                    require_source(source)
                    if previous != source['signature']:
                        if cap is not None:
                            cap.release()
                        cap = cv2.VideoCapture(source['path'])
                        previous = source['signature']
                    frame, actual = read_at(cap, source, seconds)
                    width, height = size
                    ratio = min(width / frame.shape[1], height / frame.shape[0])
                    frame = cv2.resize(frame, (max(1, int(frame.shape[1] * ratio)),
                                              max(1, int(frame.shape[0] * ratio))))
                    result = (token, actual, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), None)
                except Exception as error:
                    result = (token, seconds, None, str(error))
                    previous = None
                try:
                    self.results.put_nowait(result)
                except queue.Full:
                    try:
                        self.results.get_nowait()
                    except queue.Empty:
                        pass
                    self.results.put_nowait(result)
        finally:
            if cap is not None:
                cap.release()

    def close(self):
        self.closed.set()


class PlaybackClock:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.speed, self.position, self.anchor, self.started = 1.0, 0.0, 0.0, None

    def seek(self, seconds):
        self.position = self.anchor = float(seconds)
        self.started = None

    def shown(self, seconds):
        self.position = float(seconds)
        if self.started is None:
            self.anchor, self.started = self.position, self.clock()

    def set_speed(self, speed):
        self.speed = number(speed, 1, 10, '再生速度')
        self.anchor = self.position
        self.started = self.clock() if self.started is not None else None

    def target(self):
        return self.position if self.started is None else self.anchor + (self.clock() - self.started) * self.speed
