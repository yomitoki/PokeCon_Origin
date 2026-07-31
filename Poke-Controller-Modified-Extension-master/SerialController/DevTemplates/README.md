# PokeCon command template references

These files are examples for Dev Studio and are deliberately outside
`Commands/PythonCommands`; PokeCon will therefore not list them as executable commands.

Use **Dev Studio > Commands > New PokeCon Python Command...** to create one real
command module under `Commands/PythonCommands/tag1/tag2/tag3/`. The generator
creates exactly one class with `NAME` and `TAGS`, so it appears once in PokeCon's
**Commands > Python Command** list after **Reload Commands**.

All generator templates include `stop_checkpoint()`. Call it in every loop and
inside any long chapter/detail step so that the Commands tab's **Force stop**
button can end the command at the next safe point. `ForceStopSafePattern.py`
is a copyable reference for adding this pattern to existing commands.

`ImageDetectionCommand.py` shows `get_detection_targets()`. Add this class
method to an image-detection command and list its image paths, thresholds and
optional ROIs. PokeCon's **Commands > Image match debug** can then report every
target's live match percentage without executing the command itself.
