import re

from ade.agents.state import CodeChangeDict, PlanStepDict


def parse_xml_tag(text: str, tag: str) -> str | None:
    """Extract content between <tag>...</tag> from LLM output.

    Handles preamble text before/after the XML block.
    """
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def parse_plan(raw: str) -> list[PlanStepDict]:
    """Parse planner XML output into a list of PlanStepDict."""
    plan_content = parse_xml_tag(raw, "plan")
    if not plan_content:
        return []

    steps: list[PlanStepDict] = []
    # Extract each <step>...</step> block
    step_blocks = re.findall(r"<step>(.*?)</step>", plan_content, re.DOTALL)

    for block in step_blocks:
        try:
            step_number = _extract_int(block, "step_number", default=len(steps) + 1)
            description = parse_xml_tag(block, "description") or ""
            target_files = _extract_file_list(block)
            dependencies = _extract_dep_list(block)

            steps.append(PlanStepDict(
                step_number=step_number,
                description=description,
                target_files=target_files,
                dependencies=dependencies,
            ))
        except (ValueError, AttributeError):
            continue

    return steps


def parse_code_changes(raw: str) -> list[CodeChangeDict]:
    """Parse codegen XML output into a list of CodeChangeDict."""
    changes_content = parse_xml_tag(raw, "code_changes")
    if not changes_content:
        return []

    changes: list[CodeChangeDict] = []
    change_blocks = re.findall(r"<change>(.*?)</change>", changes_content, re.DOTALL)

    for block in change_blocks:
        try:
            file_path = parse_xml_tag(block, "file_path") or ""
            change_type = parse_xml_tag(block, "change_type") or "modify"
            diff = parse_xml_tag(block, "diff")
            full_content = parse_xml_tag(block, "full_content")

            if not file_path:
                continue

            changes.append(CodeChangeDict(
                file_path=file_path,
                change_type=change_type,
                diff=diff,
                full_content=full_content,
            ))
        except (ValueError, AttributeError):
            continue

    return changes


def _extract_int(text: str, tag: str, default: int = 0) -> int:
    """Extract an integer value from an XML tag."""
    value = parse_xml_tag(text, tag)
    if value is not None:
        try:
            return int(value.strip())
        except ValueError:
            pass
    return default


def _extract_file_list(text: str) -> list[str]:
    """Extract <file> elements from within <target_files>."""
    target_block = parse_xml_tag(text, "target_files")
    if not target_block:
        return []
    return re.findall(r"<file>(.*?)</file>", target_block, re.DOTALL)


def _extract_dep_list(text: str) -> list[int]:
    """Extract <dep> elements from within <dependencies>."""
    deps_block = parse_xml_tag(text, "dependencies")
    if not deps_block:
        return []
    dep_strs = re.findall(r"<dep>(.*?)</dep>", deps_block, re.DOTALL)
    deps: list[int] = []
    for d in dep_strs:
        try:
            deps.append(int(d.strip()))
        except ValueError:
            continue
    return deps
