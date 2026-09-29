"""Shared exception types for Studio v2 services."""


class StudioV2Error(Exception):
    """Base class for errors raised by Studio v2 services."""


class DuplicateVariableError(StudioV2Error, ValueError):
    """Raised when two kernel cells define the same variable."""

    def __init__(self, variable: str, existing_cell: str = "", new_cell: str = "") -> None:
        if existing_cell or new_cell:
            message = f"Variable '{variable}' is already defined in cell '{existing_cell}', cannot redefine it in '{new_cell}'"
        else:
            message = str(variable)
        super().__init__(message)


class DependencyCycleError(StudioV2Error, ValueError):
    """Raised when a dependency graph contains a cycle."""
