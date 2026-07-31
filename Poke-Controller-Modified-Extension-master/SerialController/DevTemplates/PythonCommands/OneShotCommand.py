"""Reference template only. Generate a usable command from Dev Studio > Commands."""
from Commands.PythonCommandBase import PythonCommand


class OneShotCommandTemplate(PythonCommand):
    NAME = "Example one-shot command"
    TAGS = ["Example"]

    @classmethod
    def get_detection_targets(cls):
        """Used only by Commands > Image match debug; normal do() never calls it."""
        return []

    def __init__(self):
        super().__init__()
        self.result = None

    def stop_checkpoint(self):
        """Use this around lengthy one-shot work as well."""
        self.checkIfAlive()

    def do(self):
        self.stop_checkpoint()
        self.result = "completed"
        print(self.result)
