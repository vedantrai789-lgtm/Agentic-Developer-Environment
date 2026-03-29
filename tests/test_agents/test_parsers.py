from ade.agents.parsers import parse_code_changes, parse_plan, parse_xml_tag


def test_parse_xml_tag_basic():
    """Should extract content from well-formed XML tags."""
    text = "<greeting>Hello, world!</greeting>"
    assert parse_xml_tag(text, "greeting") == "Hello, world!"


def test_parse_xml_tag_with_preamble():
    """Should handle text before and after the XML block."""
    text = "Here is the result:\n<answer>42</answer>\nDone."
    assert parse_xml_tag(text, "answer") == "42"


def test_parse_xml_tag_multiline():
    """Should handle multiline content."""
    text = "<code>\ndef foo():\n    return 1\n</code>"
    result = parse_xml_tag(text, "code")
    assert "def foo():" in result
    assert "return 1" in result


def test_parse_xml_tag_missing():
    """Should return None when tag is absent."""
    text = "No XML tags here."
    assert parse_xml_tag(text, "missing") is None


def test_parse_plan_valid():
    """Should parse a multi-step plan from XML."""
    raw = """Here's my plan:

<plan>
<step>
<step_number>1</step_number>
<description>Create the user model</description>
<target_files>
<file>models/user.py</file>
<file>tests/test_user.py</file>
</target_files>
<dependencies></dependencies>
</step>
<step>
<step_number>2</step_number>
<description>Add authentication endpoints</description>
<target_files>
<file>routes/auth.py</file>
</target_files>
<dependencies>
<dep>1</dep>
</dependencies>
</step>
</plan>

That's the plan!"""

    plan = parse_plan(raw)
    assert len(plan) == 2

    assert plan[0]["step_number"] == 1
    assert plan[0]["description"] == "Create the user model"
    assert "models/user.py" in plan[0]["target_files"]
    assert "tests/test_user.py" in plan[0]["target_files"]
    assert plan[0]["dependencies"] == []

    assert plan[1]["step_number"] == 2
    assert plan[1]["dependencies"] == [1]


def test_parse_plan_empty():
    """Should return empty list when no plan tag is found."""
    assert parse_plan("No plan here") == []


def test_parse_code_changes_valid():
    """Should parse code changes with diffs."""
    raw = """<code_changes>
<change>
<file_path>utils.py</file_path>
<change_type>modify</change_type>
<diff>
--- a/utils.py
+++ b/utils.py
@@ -1,3 +1,4 @@
 import os
+import sys
</diff>
</change>
</code_changes>"""

    changes = parse_code_changes(raw)
    assert len(changes) == 1
    assert changes[0]["file_path"] == "utils.py"
    assert changes[0]["change_type"] == "modify"
    assert "import sys" in changes[0]["diff"]


def test_parse_code_changes_create():
    """Should parse a 'create' change with full_content."""
    raw = """<code_changes>
<change>
<file_path>new_file.py</file_path>
<change_type>create</change_type>
<full_content>
def hello():
    print("Hello!")
</full_content>
</change>
</code_changes>"""

    changes = parse_code_changes(raw)
    assert len(changes) == 1
    assert changes[0]["change_type"] == "create"
    assert "def hello():" in changes[0]["full_content"]
    assert changes[0]["diff"] is None


def test_parse_code_changes_empty():
    """Should return empty list when no code_changes tag found."""
    assert parse_code_changes("No changes") == []
