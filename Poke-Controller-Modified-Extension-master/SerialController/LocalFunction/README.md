# LocalFunction

This folder contains portable extensions used by Dev Studio generated commands.
It does not replace or patch PokeCon's original command classes.

For an image-detection command, distribute the generated command, its template
images and `LocalFunction/ImageDetection.py`. `SimilarityHistory`,
`render_similarity_graph()` and `compose_monitor_frame()` are the common layer
for future continuous similarity logs and recordings containing camera video,
the score graph and log text.

## ZA_story on stock PokeCon 0.1.9

ZA_story keeps its compatibility layer in this folder and in `ZA_story.py`.
It does not require changes to stock PokeCon core files. Copy these runtime
folders into the destination `SerialController` directory:

- `Template/ZA_Reset_Sample`
- `Template/ZA_Story`
- `LocalFunction`
- `Commands/PythonCommands/ZA/ZA_story`

Keep the destination `Commands/PythonCommandBase.py` from stock 0.1.9.
Stock 0.1.9 does not contain `ThreadCancellation.py`, and ZA_story does not
require that file. ZA_story's normal Stop checkpoints use stock 0.1.9's
`PythonCommandBase.checkIfAlive()` and `StopThread`. `ThreadCancellation.py`
belongs only to the extended host's Force-stop/recovery UI; copying that helper
alone would not add Force stop to a stock 0.1.9 Window. Do not copy generated
`__pycache__`, `.pyc`, `.git`, or `.vscode` content with the runtime folders.
