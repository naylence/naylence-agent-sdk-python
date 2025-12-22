#!/usr/bin/env python3
"""
Generate Markdown API documentation from the public API surface.

Uses griffe to extract docstrings and generate Markdown files compatible
with Nextra documentation.

Usage:
    python scripts/generate_docs.py [--out <output_dir>]
"""

import argparse
import re
import sys
from pathlib import Path

import griffe


def escape_mdx_in_text(text: str) -> str:
    """Escape curly braces outside of code blocks for MDX compatibility.

    MDX treats {} as JSX expressions. We need to escape them as \\{ and \\}
    but only outside of ```code blocks```.
    """
    # Split into code blocks and non-code blocks
    parts = re.split(r'(```[\s\S]*?```)', text)
    result = []
    for i, part in enumerate(parts):
        if part.startswith('```'):
            # Inside code block - keep as is
            result.append(part)
        else:
            # Outside code block - escape { and }
            escaped = part.replace('{', '\\{').replace('}', '\\}')
            result.append(escaped)
    return ''.join(result)


def convert_doctest_to_codeblock(docstring: str) -> str:
    """Convert doctest-style examples (>>> ...) to Markdown code blocks.

    Finds sections that look like:
        Example:
            >>> code here
            ... continuation
            output

    And converts them to:
        **Example:**

        ```python
        code here
        continuation
        ```
    """
    lines = docstring.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a doctest block (>>> at any indentation)
        stripped = line.lstrip()
        if stripped.startswith('>>>'):
            # Collect all doctest lines
            code_lines = []
            # Track the base indentation of the first >>> line's code
            # first_code_indent = None

            while i < len(lines):
                current = lines[i]
                current_stripped = current.lstrip()

                # Check if still in doctest block
                if current_stripped.startswith('>>>'):
                    # Remove >>> prefix
                    code_after_prompt = current_stripped[3:]
                    # Remove exactly one space after >>> if present
                    if code_after_prompt.startswith(' '):
                        code_after_prompt = code_after_prompt[1:]

                    if code_after_prompt or code_after_prompt == '':
                        code_lines.append(code_after_prompt)
                    i += 1
                elif current_stripped.startswith('...'):
                    # Continuation line - remove ... prefix
                    code_after_prompt = current_stripped[3:]
                    # Remove exactly one space after ... if present
                    if code_after_prompt.startswith(' '):
                        code_after_prompt = code_after_prompt[1:]
                    code_lines.append(code_after_prompt)
                    i += 1
                elif current_stripped == '':
                    # Empty line - could be within doctest or end
                    # Look ahead to see if more doctest follows
                    if i + 1 < len(lines):
                        next_stripped = lines[i + 1].lstrip()
                        if next_stripped.startswith('>>>') or next_stripped.startswith('...'):
                            code_lines.append('')
                            i += 1
                            continue
                    # End of doctest block
                    break
                else:
                    # End of doctest block (could be output or next section)
                    break

            # Output the code block
            if code_lines:
                result.append('')
                result.append('```python')
                result.extend(code_lines)
                result.append('```')
                result.append('')
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def generate_class_doc(cls: griffe.Class) -> str:
    """Generate Markdown documentation for a class."""
    lines = []

    # Title
    lines.append(f"# {cls.name}")
    lines.append("")

    # Description
    if cls.docstring:
        lines.append(convert_doctest_to_codeblock(cls.docstring.value))
        lines.append("")

    # Inheritance
    if cls.bases:
        base_names = [str(base) for base in cls.bases]
        lines.append(f"**Extends:** {', '.join(base_names)}")
        lines.append("")

    # Constructor
    if "__init__" in cls.members:
        init = cls.members["__init__"]
        if isinstance(init, griffe.Function):
            lines.append("## Constructor")
            lines.append("")
            lines.append("```python")
            lines.append(format_function_signature(init, is_method=True))
            lines.append("```")
            lines.append("")
            if init.docstring:
                lines.append(convert_doctest_to_codeblock(init.docstring.value))
                lines.append("")

    # Properties
    properties = [
        m
        for m in cls.members.values()
        if isinstance(m, griffe.Function)
        and m.name != "__init__"
        and not m.name.startswith("_")
        and any(d.callable_path == "property" for d in m.decorators)
    ]
    if properties:
        lines.append("## Properties")
        lines.append("")
        lines.append("| Property | Type | Description |")
        lines.append("| -------- | ---- | ----------- |")
        for prop in sorted(properties, key=lambda p: p.name):
            ret_type = str(prop.returns) if prop.returns else "Any"
            desc = (
                prop.docstring.value.split("\n")[0] if prop.docstring else "-"
            )
            lines.append(f"| `{prop.name}` | `{ret_type}` | {desc} |")
        lines.append("")

    # Class attributes
    attributes = [
        m
        for m in cls.members.values()
        if isinstance(m, griffe.Attribute) and not m.name.startswith("_")
    ]
    if attributes:
        lines.append("## Attributes")
        lines.append("")
        lines.append("| Attribute | Type | Description |")
        lines.append("| --------- | ---- | ----------- |")
        for attr in sorted(attributes, key=lambda a: a.name):
            attr_type = str(attr.annotation) if attr.annotation else "Any"
            desc = attr.docstring.value.split("\n")[0] if attr.docstring else "-"
            lines.append(f"| `{attr.name}` | `{attr_type}` | {desc} |")
        lines.append("")

    # Methods
    methods = [
        m
        for m in cls.members.values()
        if isinstance(m, griffe.Function)
        and m.name != "__init__"
        and not m.name.startswith("_")
        and not any(d.callable_path == "property" for d in m.decorators)
    ]
    if methods:
        lines.append("## Methods")
        lines.append("")
        for method in sorted(methods, key=lambda m: m.name):
            lines.append(f"### {method.name}")
            lines.append("")
            lines.append("```python")
            lines.append(format_function_signature(method, is_method=True))
            lines.append("```")
            lines.append("")
            if method.docstring:
                lines.append(convert_doctest_to_codeblock(method.docstring.value))
                lines.append("")

    return "\n".join(lines)


def generate_function_doc(func: griffe.Function) -> str:
    """Generate Markdown documentation for a function."""
    lines = []

    lines.append(f"# {func.name}")
    lines.append("")

    lines.append("```python")
    lines.append(format_function_signature(func))
    lines.append("```")
    lines.append("")

    if func.docstring:
        lines.append(convert_doctest_to_codeblock(func.docstring.value))
        lines.append("")

    return "\n".join(lines)


def generate_alias_doc(name: str, alias: griffe.Alias) -> str:
    """Generate Markdown documentation for an alias (re-exported symbol)."""
    target = alias.target
    if isinstance(target, griffe.Class):
        return generate_class_doc(target)
    elif isinstance(target, griffe.Function):
        return generate_function_doc(target)
    else:
        # For other types (constants, etc.)
        lines = []
        lines.append(f"# {name}")
        lines.append("")
        if alias.docstring:
            lines.append(convert_doctest_to_codeblock(alias.docstring.value))
        elif hasattr(target, "docstring") and target.docstring:
            lines.append(convert_doctest_to_codeblock(target.docstring.value))
        else:
            lines.append(f"Alias for `{alias.target_path}`")
        lines.append("")
        return "\n".join(lines)


def format_function_signature(func: griffe.Function, is_method: bool = False) -> str:
    """Format a function signature."""
    params = []
    for param in func.parameters:
        if param.name in ("self", "cls"):
            continue
        param_str = param.name
        if param.annotation:
            param_str += f": {param.annotation}"
        if param.default is not None:
            default_str = str(param.default)
            # Truncate long defaults
            if len(default_str) > 30:
                default_str = "..."
            param_str += f" = {default_str}"
        params.append(param_str)

    params_str = ", ".join(params)
    ret = f" -> {func.returns}" if func.returns else ""

    if is_method:
        return f"def {func.name}({params_str}){ret}"
    else:
        return f"def {func.name}({params_str}){ret}"


def generate_index(members: dict, module_name: str) -> str:
    """Generate index page for the API reference."""
    lines = []
    lines.append(f"# {module_name} API Reference")
    lines.append("")
    lines.append(
        "This section contains the auto-generated API documentation for the "
        "**naylence-agent-sdk** Python package."
    )
    lines.append("")

    # Group by type
    classes = []
    functions = []
    other = []

    for name, member in members.items():
        if isinstance(member, griffe.Alias):
            target = member.target
            if isinstance(target, griffe.Class):
                classes.append(name)
            elif isinstance(target, griffe.Function):
                functions.append(name)
            else:
                other.append(name)
        elif isinstance(member, griffe.Class):
            classes.append(name)
        elif isinstance(member, griffe.Function):
            functions.append(name)
        else:
            other.append(name)

    if classes:
        lines.append("## Classes")
        lines.append("")
        lines.append("| Class | Description |")
        lines.append("| ----- | ----------- |")
        for name in sorted(classes):
            member = members[name]
            target = member.target if isinstance(member, griffe.Alias) else member
            desc = "-"
            if hasattr(target, "docstring") and target.docstring:
                desc = target.docstring.value.split("\n")[0]
            lines.append(f"| [{name}](classes/{name}/) | {desc} |")
        lines.append("")

    if functions:
        lines.append("## Functions")
        lines.append("")
        lines.append("| Function | Description |")
        lines.append("| -------- | ----------- |")
        for name in sorted(functions):
            member = members[name]
            target = member.target if isinstance(member, griffe.Alias) else member
            desc = "-"
            if hasattr(target, "docstring") and target.docstring:
                desc = target.docstring.value.split("\n")[0]
            lines.append(f"| [{name}](functions/{name}/) | {desc} |")
        lines.append("")

    if other:
        lines.append("## Other")
        lines.append("")
        lines.append("| Name | Description |")
        lines.append("| ---- | ----------- |")
        for name in sorted(other):
            member = members[name]
            target = member.target if isinstance(member, griffe.Alias) else member
            desc = "-"
            if hasattr(target, "docstring") and target.docstring:
                desc = target.docstring.value.split("\n")[0]
            lines.append(f"| [{name}](other/{name}/) | {desc} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Markdown API documentation"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="docs/api",
        help="Output directory for generated docs",
    )
    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the public API module
    try:
        loader = griffe.GriffeLoader(
            search_paths=[str(Path(__file__).parent.parent / "src")]
        )
        module = loader.load("naylence.agent.public_api")
    except Exception as e:
        print(f"Error loading module: {e}", file=sys.stderr)
        sys.exit(1)

    # Get exported members from __all__
    all_exports = module.members.get("__all__")
    if all_exports and hasattr(all_exports, "value"):
        export_names = [
            s.strip().strip("'\"") for s in str(all_exports.value).strip("[]").split(",") # type: ignore
        ]
    else:
        export_names = [
            name for name in module.members.keys() if not name.startswith("_")
        ]

    # Collect members
    members = {}
    for name in export_names:
        if name in module.members:
            members[name] = module.members[name]

    # Generate index
    index_content = generate_index(members, "Python Agent SDK")
    (output_dir / "page.mdx").write_text(escape_mdx_in_text(index_content))
    print(f"Generated: {output_dir / 'page.mdx'}")

    # Create subdirectories
    classes_dir = output_dir / "classes"
    functions_dir = output_dir / "functions"
    other_dir = output_dir / "other"

    classes_dir.mkdir(exist_ok=True)
    functions_dir.mkdir(exist_ok=True)
    other_dir.mkdir(exist_ok=True)

    # Generate individual docs
    classes_meta = {}
    functions_meta = {}
    other_meta = {}

    for name, member in members.items():
        if isinstance(member, griffe.Alias):
            target = member.target
            if isinstance(target, griffe.Class):
                doc = generate_class_doc(target)
                doc_dir = classes_dir / name
                doc_dir.mkdir(exist_ok=True)
                (doc_dir / "page.mdx").write_text(escape_mdx_in_text(doc))
                classes_meta[name] = name
                print(f"Generated: {doc_dir / 'page.mdx'}")
            elif isinstance(target, griffe.Function):
                doc = generate_function_doc(target)
                doc_dir = functions_dir / name
                doc_dir.mkdir(exist_ok=True)
                (doc_dir / "page.mdx").write_text(escape_mdx_in_text(doc))
                functions_meta[name] = name
                print(f"Generated: {doc_dir / 'page.mdx'}")
            else:
                doc = generate_alias_doc(name, member)
                doc_dir = other_dir / name
                doc_dir.mkdir(exist_ok=True)
                (doc_dir / "page.mdx").write_text(escape_mdx_in_text(doc))
                other_meta[name] = name
                print(f"Generated: {doc_dir / 'page.mdx'}")
        elif isinstance(member, griffe.Class):
            doc = generate_class_doc(member)
            doc_dir = classes_dir / name
            doc_dir.mkdir(exist_ok=True)
            (doc_dir / "page.mdx").write_text(escape_mdx_in_text(doc))
            classes_meta[name] = name
            print(f"Generated: {doc_dir / 'page.mdx'}")
        elif isinstance(member, griffe.Function):
            doc = generate_function_doc(member)
            doc_dir = functions_dir / name
            doc_dir.mkdir(exist_ok=True)
            (doc_dir / "page.mdx").write_text(escape_mdx_in_text(doc))
            functions_meta[name] = name
            print(f"Generated: {doc_dir / 'page.mdx'}")

    # Generate _meta.js files
    generate_meta_js(output_dir, {
        "index": {"title": "Python Reference", "theme": {"breadcrumb": True}},
        "classes": "Classes",
        "functions": "Functions",
        "other": "Other",
    })

    if classes_meta:
        generate_meta_js(classes_dir, classes_meta)
    if functions_meta:
        generate_meta_js(functions_dir, functions_meta)
    if other_meta:
        generate_meta_js(other_dir, other_meta)

    # Remove empty directories
    for d in [classes_dir, functions_dir, other_dir]:
        if d.exists() and not any(d.iterdir()):
            d.rmdir()

    print(f"\nDone! Documentation generated in {output_dir}")


def generate_meta_js(directory: Path, entries: dict):
    """Generate a Nextra _meta.js file."""

    def to_js_value(v):
        """Convert Python value to JavaScript literal string."""
        if isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, str):
            return repr(v)
        elif isinstance(v, dict):
            inner = ", ".join(f"{k}: {to_js_value(val)}" for k, val in v.items())
            return f"{{ {inner} }}"
        else:
            return repr(v)

    lines = ["// Auto-generated navigation", "export default {"]
    for key, value in entries.items():
        if isinstance(value, dict):
            lines.append(f"  '{key}': {to_js_value(value)},")
        else:
            lines.append(f"  '{key}': '{value}',")
    lines.append("};")
    (directory / "_meta.js").write_text("\n".join(lines))
    print(f"Generated: {directory / '_meta.js'}")


if __name__ == "__main__":
    main()
