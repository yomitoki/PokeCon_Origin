# CommandsAssist commands

Place lightweight recovery commands in this folder. Each file must define a
subclass of `Commands.PythonCommandBase.PythonCommand` with a non-empty `NAME`.

When an OR trigger is satisfied, PokeCon stops the current command and active
recording, runs the selected recovery command, then restarts the original
command. Recording resumes in a new file. A normal return from `do()` counts as
successful completion. Long-running loops should call `checkIfAlive()`.
