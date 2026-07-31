"""Reference template only. Generate a usable command from Dev Studio > Commands."""
from Commands.PythonCommandBase import PythonCommand


class StepCommandTemplate(PythonCommand):
    NAME = "Example step command"
    TAGS = ["Example"]
    STEP_LABELS = ["Chapter 1: preparation", "Chapter 2: detailed task"]

    @classmethod
    def get_detection_targets(cls):
        """Used only by Commands > Image match debug; normal do() never calls it."""
        return []

    def __init__(self):
        super().__init__()
        self.step = 0

    def stop_checkpoint(self):
        """Call in long tasks / 長い章・詳細処理の途中で呼びます。"""
        self.checkIfAlive()

    def do(self):
        while self.alive and 0 <= self.step < len(self.STEP_LABELS):
            self.stop_checkpoint()
            previous_step = self.step
            print("[STEP] {}/{}: {}".format(self.step + 1, len(self.STEP_LABELS), self.STEP_LABELS[self.step]))
            next_step = getattr(self, "_step_{}".format(self.step))()
            if next_step is None:
                self.step += 1
            elif isinstance(next_step, str):
                self.step = self.STEP_LABELS.index(next_step)
            else:
                self.step = int(next_step)
            if self.step != previous_step:
                target_label = "complete" if self.step >= len(self.STEP_LABELS) else self.step + 1
                print("[STEP] transition: {} -> {}".format(previous_step + 1, target_label))
            self.wait(0.01)

    def _step_0(self):
        # Chapter 1: preparation / 第1章: 準備
        self.stop_checkpoint()
        return None  # next / 次へ。self.stepで繰り返し、1で番号1へ移動。

    def _step_1(self):
        # Chapter 2: detailed task / 第2章: 詳細処理
        self.stop_checkpoint()
        return None
