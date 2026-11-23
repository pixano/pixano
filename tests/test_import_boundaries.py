# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The import boundaries of the architecture spec, checked as its rule ARCH-51 asks.

- ARCH-48: `pixano.schemas` holds the schemas, which are Pydantic and Lance models. It imports no
  heavy native, graphical or server dependency, and no new library that a model is not made of.
- ARCH-47: `pixano` and `pixano-worker` import nothing from `pixano-inference` but its client and
  its schemas.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).parents[1]

# ARCH-48 names OpenCV and FastAPI. Starlette and Uvicorn are the rest of the server, and
# pycocotools is a compiled library that only the conversion of a mask calls.
HEAVY_MODULES = ("cv2", "pycocotools", "fastapi", "starlette", "uvicorn")

# What a schema is made of: Pydantic models and Lance models. pyarrow gives a Lance model its types.
SCHEMA_LIBRARIES = {"pydantic", "lancedb", "pyarrow", "typing_extensions"}

# What the code of the models still imports and that no model is made of: opening an image
# (Pillow), the geometry of a box or a mask (NumPy), making an identifier (shortuuid). The tech lead
# decided that `pixano.schemas` holds schemas only, so this list never grows. Take a name out when
# the schemas no longer import it.
NOT_A_SCHEMA_LIBRARY_YET = {"numpy", "PIL", "shortuuid"}

# Runs a statement where the heavy modules cannot be imported. Its last line of output lists each
# heavy module that was asked for, with the place that asked. A refused import that the code catches
# is listed too: on a machine that has the module, the same line would load it.
_PROBE = """
import json
import sys
import traceback

statement, heavy = sys.argv[1], set(sys.argv[2:])
asked = []


class RefuseHeavyModules:
    @staticmethod
    def find_spec(name, path=None, target=None):
        if name.partition(".")[0] not in heavy:
            return None
        callers = [f for f in traceback.extract_stack()[:-1] if not f.filename.startswith("<frozen importlib")]
        asked.append(f"{name}, at {callers[-1].filename}:{callers[-1].lineno}")
        raise ModuleNotFoundError(f"No module named {name!r}: this check refuses it", name=name)


sys.meta_path.insert(0, RefuseHeavyModules)
try:
    exec(compile(statement, "<statement>", "exec"))
finally:
    print(json.dumps(asked))
"""

# Runs a statement, and lists the libraries that the modules of `pixano` ask for while it runs, each
# with the modules that asked. Every `import` statement that runs is seen, also for a library that
# another one loaded first. The standard library and `pixano` itself are left out.
_RECORDER = """
import builtins
import json
import sys

statement = sys.argv[1]
asked = {}
import_module = builtins.__import__


def record(name, globals=None, locals=None, fromlist=(), level=0):
    by = (globals or {}).get("__name__", "")
    library = name.partition(".")[0]
    is_pixano = by == "pixano" or by.startswith("pixano.")
    if level == 0 and is_pixano and library != "pixano" and library not in sys.stdlib_module_names:
        asked.setdefault(library, set()).add(by)
    return import_module(name, globals, locals, fromlist, level)


builtins.__import__ = record
try:
    exec(compile(statement, "<statement>", "exec"))
finally:
    print(json.dumps({library: sorted(by) for library, by in asked.items()}))
"""

INFERENCE_PACKAGE = "pixano_inference"
ALLOWED_INFERENCE_MODULES = ("pixano_inference.client", "pixano_inference.schemas")
SOURCE_TREES = (REPOSITORY / "src" / "pixano", REPOSITORY / "packages" / "pixano-worker" / "src")


def _run_without_heavy_modules(statement: str) -> tuple[list[str], str]:
    """Run a statement in a new interpreter that refuses the heavy modules.

    Returns:
        The heavy modules the statement asked for, and what the interpreter wrote on its error
        output if the statement failed.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, statement, *HEAVY_MODULES],
        capture_output=True,
        text=True,
        timeout=120,
    )
    lines = result.stdout.splitlines()
    return json.loads(lines[-1]) if lines else [], result.stderr if result.returncode else ""


def _libraries_asked_by_pixano(statement: str) -> dict[str, list[str]]:
    """Run a statement in a new interpreter, and list the libraries the modules of `pixano` ask for.

    Returns:
        For each library, by the name of its top package, the modules of `pixano` that imported it.
    """
    result = subprocess.run(
        [sys.executable, "-c", _RECORDER, statement],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"`{statement}` failed:\n{result.stderr}"
    return json.loads(result.stdout.splitlines()[-1])


def test_schemas_import_no_heavy_module():
    asked, error = _run_without_heavy_modules("import pixano.schemas")

    assert not asked, "ARCH-48: `import pixano.schemas` imports " + "; ".join(asked)
    assert not error, f"`import pixano.schemas` failed:\n{error}"


def test_schemas_import_no_new_library_that_a_model_is_not_made_of():
    asked = _libraries_asked_by_pixano("import pixano.schemas")

    new = {library: by for library, by in asked.items() if library not in SCHEMA_LIBRARIES | NOT_A_SCHEMA_LIBRARY_YET}
    assert not new, (
        "ARCH-48: `pixano.schemas` holds schemas only, Pydantic and Lance models. Importing it imports "
        + "; ".join(f"{library}, asked by {', '.join(by)}" for library, by in sorted(new.items()))
        + ". Import it where it is used, out of the schemas."
    )

    gone = sorted(NOT_A_SCHEMA_LIBRARY_YET - set(asked))
    assert not gone, f"`import pixano.schemas` no longer imports {', '.join(gone)}: take it out of the list."


@pytest.mark.parametrize(
    ("statement", "asked"),
    [
        # A module of pixano asks for a library: it is listed, with the module that asked.
        (
            "exec('import shortuuid', {'__name__': 'pixano.schemas.planted'})",
            {"shortuuid": ["pixano.schemas.planted"]},
        ),
        # A library that is loaded already is still seen when a module of pixano imports it.
        (
            "import shortuuid\nexec('from shortuuid import uuid', {'__name__': 'pixano.planted'})",
            {"shortuuid": ["pixano.planted"]},
        ),
        # Not a module of pixano, the standard library, pixano itself: none is listed.
        ("exec('import shortuuid', {'__name__': 'pixano_tools.planted'})", {}),
        ("exec('import json', {'__name__': 'pixano.planted'})", {}),
        ("exec('import pixano.utils', {'__name__': 'pixano.planted'})", {}),
    ],
)
def test_the_recorder_lists_what_a_module_of_pixano_asks_for(statement, asked):
    assert _libraries_asked_by_pixano(statement) == asked


@pytest.mark.parametrize(
    ("statement", "reported", "fails"),
    [
        ("import cv2", "cv2, at <statement>:1", True),
        ("from pycocotools import mask", "pycocotools, at <statement>:1", True),
        ("from fastapi.encoders import jsonable_encoder", "fastapi, at <statement>:1", True),
        # Caught by the code: the statement succeeds, and the import is still reported.
        ("try:\n    import uvicorn\nexcept ImportError:\n    uvicorn = None", "uvicorn, at <statement>:2", False),
    ],
)
def test_the_probe_reports_a_heavy_import(statement, reported, fails):
    asked, error = _run_without_heavy_modules(statement)

    assert asked == [reported]
    assert bool(error) is fails


def _is_under(name: str, module: str) -> bool:
    return name == module or name.startswith(f"{module}.")


def _refused_inference_imports(source: str) -> list[tuple[int, str]]:
    """List the imports of `pixano_inference` that ARCH-47 refuses, as (line, name).

    The name is what the statement asks for: `from a import b` asks for `a.b`. A relative import is
    never one of `pixano_inference`: `pixano` has a module of that name, in `inference/providers/`.
    An import by name (`import_module`, `__import__`) is seen when the name is a literal.
    """
    refused = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [f"{node.module}.{alias.name}" for alias in node.names]
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) in ("import_module", "__import__")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names = [node.args[0].value]
        else:
            continue
        refused += [
            (node.lineno, name)
            for name in names
            if _is_under(name, INFERENCE_PACKAGE)
            and not any(_is_under(name, allowed) for allowed in ALLOWED_INFERENCE_MODULES)
        ]
    return refused


def test_pixano_and_the_worker_import_only_the_client_and_the_schemas_of_pixano_inference():
    refused = []
    for tree in SOURCE_TREES:
        files = sorted(tree.rglob("*.py"))
        assert files, f"{tree} holds no Python file: the check would pass on nothing"
        for file in files:
            refused += [
                f"{file.relative_to(REPOSITORY)}:{line} imports {name}"
                for line, name in _refused_inference_imports(file.read_text(encoding="utf-8"))
            ]

    assert not refused, (
        f"ARCH-47: only {' and '.join(ALLOWED_INFERENCE_MODULES)} may be imported from pixano-inference.\n"
        + "\n".join(refused)
    )


@pytest.mark.parametrize(
    "source",
    [
        "import pixano_inference.client",
        "import pixano_inference.schemas.detection as detection",
        "from pixano_inference import client, schemas",
        "from pixano_inference.client import SyncPixanoInferenceClient",
        "from pixano_inference.schemas.detection import DetectionRequest",
        "import_module('pixano_inference.client')",
        # Modules of pixano that only share the name.
        "from .pixano_inference import PixanoInferenceProvider",
        "from pixano.inference.providers.pixano_inference import PixanoInferenceProvider",
        "import pixano_inference_extras",
    ],
)
def test_an_allowed_import_of_pixano_inference_passes(source):
    assert _refused_inference_imports(source) == []


@pytest.mark.parametrize(
    ("source", "name"),
    [
        ("import pixano_inference", "pixano_inference"),
        ("import pixano_inference.models", "pixano_inference.models"),
        ("import pixano_inference.client_internals", "pixano_inference.client_internals"),
        ("from pixano_inference import PixanoInferenceClient", "pixano_inference.PixanoInferenceClient"),
        ("from pixano_inference import *", "pixano_inference.*"),
        ("from pixano_inference.models.sam2 import SAM2", "pixano_inference.models.sam2.SAM2"),
        ("def load():\n    from pixano_inference import settings", "pixano_inference.settings"),
        ("if TYPE_CHECKING:\n    import pixano_inference.app", "pixano_inference.app"),
        ("importlib.import_module('pixano_inference.app')", "pixano_inference.app"),
        ("__import__('pixano_inference')", "pixano_inference"),
    ],
)
def test_another_import_of_pixano_inference_is_refused(source, name):
    assert [found for _, found in _refused_inference_imports(source)] == [name]
