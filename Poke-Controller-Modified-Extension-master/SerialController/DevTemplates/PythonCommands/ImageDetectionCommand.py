"""Reference for commands that expose targets to Commands > Image match debug."""
import os

from Commands.PythonCommandBase import PythonCommand


class ImageDetectionCommandTemplate(PythonCommand):
    NAME = "Image detection command (reference only)"
    TAGS = ["Example", "ImageDetection"]

    @classmethod
    def get_detection_targets(cls):
        # The debug mode calls this without constructing/running this command.
        return [{
            "name": "example target",
            "path": os.path.join(os.path.dirname(__file__), "Template", "target.png"),
            "threshold": 0.80,
            "roi": (0, 0, 0, 0),
        }]

    def do(self):
        self.checkIfAlive()
        # Normal image-detection command processing goes here.
