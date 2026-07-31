"""Reference: make existing commands respond to the Commands > Force stop button."""
from Commands.PythonCommandBase import PythonCommand


class ForceStopSafePattern(PythonCommand):
    NAME = "Force-stop safe pattern (reference only)"
    TAGS = ["Example", "ForceStop"]

    def stop_checkpoint(self):
        # Put this helper into existing commands, then call it often.
        self.checkIfAlive()

    def do(self):
        for chapter in range(10):
            self.stop_checkpoint()
            self._long_chapter(chapter)

    def _long_chapter(self, chapter):
        for detail in range(100):
            self.stop_checkpoint()  # Required inside nested/long loops too.
            # Do a small, interruptible piece of work here.
            pass
