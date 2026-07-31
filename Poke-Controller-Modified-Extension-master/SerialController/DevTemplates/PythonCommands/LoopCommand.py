"""Reference template only. Generate a usable command from Dev Studio > Commands."""
from Commands.PythonCommandBase import PythonCommand


class LoopCommandTemplate(PythonCommand):
    NAME = "Example loop command"
    TAGS = ["Example"]

    @classmethod
    def get_detection_targets(cls):
        """Used only by Commands > Image match debug; normal do() never calls it."""
        return []

    def __init__(self):
        super().__init__()
        self.loop_count = 0

    def stop_checkpoint(self):
        """Call from every repeat or potentially long operation."""
        self.checkIfAlive()

    def do(self):
        while self.alive:
            self.stop_checkpoint()
            self.loop_count += 1
            print("loop_count = {}".format(self.loop_count))
            self.wait(1.0)
