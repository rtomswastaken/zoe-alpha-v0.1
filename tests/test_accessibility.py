"""Unit tests for accessibility inspection."""

from zoe.macos.accessibility import (
    get_app_accessibility_tree,
    find_elements_by_role,
    find_element_by_title,
    AX_ERRORS,
)


def test_ax_error_mapping():
    assert 0 in AX_ERRORS
    assert -25211 in AX_ERRORS
    assert "Accessibility permission" in AX_ERRORS[-25211]


def test_tree_search_helpers():
    sample_tree = {
        "role": "AXApplication",
        "title": "Safari",
        "children": [
            {
                "role": "AXWindow",
                "title": "YouTube",
                "children": [
                    {
                        "role": "AXButton",
                        "title": "Full Screen",
                        "bounds": {"x": 500, "y": 400, "width": 50, "height": 30},
                        "center": {"x": 525, "y": 415},
                    },
                    {
                        "role": "AXButton",
                        "title": "Play",
                        "bounds": {"x": 200, "y": 400, "width": 40, "height": 40},
                        "center": {"x": 220, "y": 420},
                    },
                ],
            }
        ],
    }

    buttons = find_elements_by_role(sample_tree, "AXButton")
    assert len(buttons) == 2

    fs_btn = find_element_by_title(sample_tree, "Full Screen")
    assert fs_btn is not None
    assert fs_btn["center"]["x"] == 525


def test_get_accessibility_tree_structure():
    # Calling get_app_accessibility_tree should always return a structured dict
    res = get_app_accessibility_tree()
    assert isinstance(res, dict)
    assert "success" in res
    assert res["action"] == "get_accessibility_tree"
    if not res["success"]:
        assert "error" in res
