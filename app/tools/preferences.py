# app/tools/preferences.py
"""Tool handlers for user preferences.

The project currently does not have a dedicated preferences service, so the
handlers are thin stubs that raise a clear NotImplementedError. This satisfies
the import requirements while making the missing functionality obvious for
future development.
"""

from app.tools.schemas import (
    GetPreferenceInput,
    SetPreferenceInput,
    GetUserPreferencesInput,
    UpdateUserPreferencesInput,
)


def get_user_preferences(inp: GetPreferenceInput) -> dict:
    raise NotImplementedError("User preferences service not yet implemented")


def update_user_preferences(inp: SetPreferenceInput) -> dict:
    raise NotImplementedError("User preferences service not yet implemented")
