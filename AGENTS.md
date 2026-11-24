## Mandatory Python Validation

After creating or modifying Python code:

- Run `uvx pyright --pythonpath "$(which python)"`.
- Examine all reported errors.
- Correct type errors introduced by your changes.
- Verify that called methods exist on their respective classes.
- Verify method signatures against their actual definitions.
- Repeat validation after making corrections.
- Never suppress type errors to pass validation.
- Report any remaining errors before declaring the task complete.
- Do not modify unrelated code solely to resolve pre-existing errors.

## Mandatory Unit Testing

After modifying Python code:

- Run relevant unit tests using `uv run pytest`.
- Inspect test failures and determine their root causes.
- Correct failures introduced by the changes.
- Do not weaken assertions merely to make tests pass.
- Do not bypass constructors to conceal initialization errors.
- Distinguish pre-existing failures from newly introduced failures.
- Never claim functional correctness based solely on static analysis.
- Report any tests that could not be executed successfully.