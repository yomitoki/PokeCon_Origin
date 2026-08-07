# CommandsAssist commands

Place lightweight replacement commands in this folder. Each file must define a
subclass of `Commands.PythonCommandBase.PythonCommand` with a non-empty `NAME`.

Each trigger can either pause the current command or pause it and run a selected
replacement command. The original command remains alive and resumes at its
current Step checkpoint after replacement completes, instead of restarting from
`do()`. A normal return from replacement `do()` counts as successful completion.
Long-running loops should call `checkIfAlive()`.

Recording variable rules may link their normal end condition to one of these
triggers. A discard condition never runs the linked action.

The function-replacement dialog can select multiple state-table keys at once.
Each generated mapping can then choose either a CommandsAssist Python command
or a registered PC-controller recording. Controller recordings are managed from
Manual Control, can be angle-adjusted by line range, copied as Python code, and
deleted together with mappings that reference them.

## Interactive Step debugging

Use **CommandsAssist > かんたんStepデバッグ** when returning to a scenario
problem is expensive. It stops immediately before a configured state method,
lists that method's operations, and lets the user run one operation or a range.
Temporary code and PC-controller-recording replacements are stored separately
from the production Python source and are included in InputSet snapshots.

The permanent Japanese walkthrough is in [STEP_DEBUG_GUIDE.md](STEP_DEBUG_GUIDE.md).
