import pytest
from app.tools.registry import (
    registry,
    list_tools,
    execute,
    get,
    ToolRegistry,
    ToolDefinition,
)
from app.tools import registry as package_registry


def test_registry_singleton_list_tools():
    tools = registry.list_tools()
    assert len(tools) > 0
    names = [t["name"] for t in tools]
    assert "search_products" in names
    assert "create_draft_bill" in names
    assert "find_customer" in names
    assert "get_daily_sales" in names
    assert "get_user_preferences" in names


def test_module_level_list_tools():
    tools = list_tools()
    assert len(tools) > 0
    names = [t["name"] for t in tools]
    assert "search_products" in names


def test_tool_definitions_valid_schema():
    tools = registry.list_tools()
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert isinstance(tool["input_schema"], dict)


def test_execute_unknown_tool():
    res = execute("non_existent_tool", {})
    assert not res.success
    assert res.error.code == "UNKNOWN_TOOL"


def test_execute_invalid_args():
    res = execute("get_stock", {"invalid_field": 123})
    assert not res.success
    assert res.error.code == "INVALID_TOOL_ARGUMENTS"
