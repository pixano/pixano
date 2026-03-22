# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Generate structured JSON API documentation from Python source code.

Uses griffe to parse Python source and extract docstrings, classes, functions,
parameters, return types, etc. Outputs JSON files that Astro can consume
to render beautiful API reference pages.

Usage:
    python scripts/generate_api_docs.py

Outputs to: src/data/api/
"""

import json
import sys
from pathlib import Path
from typing import Any

import griffe


# Configuration
SRC_PATH = Path(__file__).parent.parent.parent / "src" / "pixano"
OUTPUT_DIR = Path(__file__).parent.parent / "src" / "data" / "api"
IGNORED_FILES = {"__init__.py", "__version__.py", "__main__.py"}
IGNORED_DIRS = {"__pycache__"}


def extract_docstring(obj) -> str:
    """Extract docstring text from a griffe object."""
    if obj.docstring:
        return obj.docstring.value.strip()
    return ""


def extract_parameters(func) -> list[dict]:
    """Extract function parameters with types and defaults."""
    params = []
    for param in func.parameters:
        if param.name in ("self", "cls"):
            continue
        p = {
            "name": param.name,
            "annotation": str(param.annotation) if param.annotation else None,
            "default": str(param.default) if param.default else None,
            "kind": str(param.kind),
        }
        params.append(p)
    return params


def extract_return_type(func) -> str | None:
    """Extract return type annotation."""
    if func.returns:
        return str(func.returns)
    return None


def extract_function(func) -> dict:
    """Extract function data."""
    return {
        "name": func.name,
        "docstring": extract_docstring(func),
        "parameters": extract_parameters(func),
        "returns": extract_return_type(func),
        "is_async": getattr(func, "is_async", False),
        "decorators": [str(d.value) for d in func.decorators] if hasattr(func, "decorators") else [],
        "lineno": func.lineno,
    }


def extract_attribute(attr) -> dict:
    """Extract class/module attribute data."""
    return {
        "name": attr.name,
        "annotation": str(attr.annotation) if attr.annotation else None,
        "value": str(attr.value) if hasattr(attr, "value") and attr.value else None,
        "docstring": extract_docstring(attr) if hasattr(attr, "docstring") else "",
    }


def extract_class(cls) -> dict:
    """Extract class data including methods and attributes."""
    methods = []
    attributes = []
    class_methods = []
    static_methods = []
    properties = []

    for member_name, member in sorted(cls.members.items()):
        if member_name.startswith("_") and not member_name.startswith("__"):
            continue  # Skip private members
        if member_name.startswith("__") and member_name != "__init__":
            continue  # Skip dunder methods except __init__

        if isinstance(member, griffe.Function):
            func_data = extract_function(member)
            if any("classmethod" in str(d) for d in (member.decorators or [])):
                class_methods.append(func_data)
            elif any("staticmethod" in str(d) for d in (member.decorators or [])):
                static_methods.append(func_data)
            elif any("property" in str(d) for d in (member.decorators or [])):
                properties.append(func_data)
            else:
                methods.append(func_data)
        elif isinstance(member, griffe.Attribute):
            attributes.append(extract_attribute(member))

    # Extract base classes
    bases = []
    if hasattr(cls, "bases") and cls.bases:
        bases = [str(b) for b in cls.bases]

    return {
        "name": cls.name,
        "docstring": extract_docstring(cls),
        "bases": bases,
        "attributes": attributes,
        "methods": methods,
        "class_methods": class_methods,
        "static_methods": static_methods,
        "properties": properties,
        "decorators": [str(d.value) for d in cls.decorators] if hasattr(cls, "decorators") else [],
        "lineno": cls.lineno,
    }


def extract_module(module) -> dict:
    """Extract full module data."""
    classes = []
    functions = []
    attributes = []
    submodules = []

    for member_name, member in sorted(module.members.items()):
        if member_name.startswith("_"):
            continue

        if isinstance(member, griffe.Class):
            classes.append(extract_class(member))
        elif isinstance(member, griffe.Function):
            functions.append(extract_function(member))
        elif isinstance(member, griffe.Attribute):
            attributes.append(extract_attribute(member))
        elif isinstance(member, griffe.Module):
            submodules.append(member_name)

    return {
        "module": module.path,
        "docstring": extract_docstring(module),
        "filepath": str(module.filepath) if module.filepath else None,
        "classes": classes,
        "functions": functions,
        "attributes": attributes,
        "submodules": submodules,
    }


def build_nav_tree(modules: list[dict]) -> list[dict]:
    """Build a navigation tree from flat module list."""
    tree: dict[str, Any] = {}
    for mod in modules:
        parts = mod["module"].replace("pixano.", "").split(".")
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {"_children": {}, "_module": None}
            current = current[part]["_children"]
        # Mark the leaf
        parent = tree
        for part in parts[:-1]:
            parent = parent[part]["_children"]
        if parts[-1] in parent:
            parent[parts[-1]]["_module"] = mod["module"]
        else:
            parent[parts[-1]] = {"_children": {}, "_module": mod["module"]}

    def tree_to_list(node, prefix=""):
        items = []
        for key, val in sorted(node.items()):
            path = f"{prefix}.{key}" if prefix else key
            item = {
                "title": key,
                "slug": path.replace(".", "/"),
                "module": val.get("_module"),
                "children": tree_to_list(val["_children"], path),
            }
            items.append(item)
        return items

    return tree_to_list(tree)


def main():
    """Main entry point."""
    print(f"Scanning Python source: {SRC_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")

    if not SRC_PATH.exists():
        print(f"ERROR: Source path does not exist: {SRC_PATH}")
        sys.exit(1)

    # Clean output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob("*.json"):
        f.unlink()

    # Load the package with griffe
    try:
        package = griffe.load(
            "pixano",
            search_paths=[str(SRC_PATH.parent)],
            docstring_parser="google",
        )
    except Exception as e:
        print(f"ERROR: Failed to load package: {e}")
        sys.exit(1)

    all_modules = []
    module_count = 0

    def process_module(module, depth=0):
        nonlocal module_count
        # Skip private modules
        if module.name.startswith("_") and module.name != "__init__":
            return

        data = extract_module(module)

        # Only write if module has actual content
        has_content = data["classes"] or data["functions"] or data["attributes"]
        if has_content or depth == 0:
            # Create output filename from module path
            filename = module.path.replace(".", "_") + ".json"
            output_path = OUTPUT_DIR / filename

            output_path.write_text(json.dumps(data, indent=2, default=str, sort_keys=True) + "\n")
            all_modules.append(data)
            module_count += 1
            print(
                f"  {'  ' * depth}{'[pkg]' if data['submodules'] else '[mod]'} {module.path} "
                f"({len(data['classes'])} classes, {len(data['functions'])} functions)"
            )

        # Process submodules
        for member_name, member in sorted(module.members.items()):
            if isinstance(member, griffe.Module) and not member_name.startswith("_"):
                process_module(member, depth + 1)

    print("\nProcessing modules:")
    process_module(package)

    # Write navigation index
    nav_tree = build_nav_tree(all_modules)
    nav_path = OUTPUT_DIR / "_nav.json"
    nav_path.write_text(json.dumps(nav_tree, indent=2, sort_keys=True) + "\n")
    print(f"\nNavigation tree written to: {nav_path}")

    # Write module index
    index_path = OUTPUT_DIR / "_index.json"
    index_data = [
        {
            "module": m["module"],
            "docstring": m["docstring"][:200] if m["docstring"] else "",
            "classes": len(m["classes"]),
            "functions": len(m["functions"]),
        }
        for m in all_modules
    ]
    index_path.write_text(json.dumps(index_data, indent=2, sort_keys=True) + "\n")

    print(f"\nDone! Generated {module_count} module files.")
    print(f"Index written to: {index_path}")


if __name__ == "__main__":
    main()
