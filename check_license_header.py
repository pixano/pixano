# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pathlib import Path


ROOT = Path(__file__).parent

# Headers for each file type
HEADERS = {
    ".py": """# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
\n""",
    ".svelte": """<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->
\n""",
    ".ts": """/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/
\n""",
}

# Files to exclude
EXCLUDE_FILES = {
    "vite.config.ts",
    "vite-env.d.ts",
    "vite.env.d.ts",
    "ambient.d.ts",
    "$types.d.ts",
    "app.d.ts",
    "io.test.ts",
}

# Files to exclude
EXCLUDE_PATHS = {
    "node_modules",
    ".svelte-kit",
    ".venv",
}


def check_header(file_path: Path, header: str):
    """Check if the file contains the required header."""
    with file_path.open("r", encoding="utf-8") as file:
        content = file.read()
        return content.startswith(header) or content == header[:-1]


def main():
    """Check if all files contain the required headers."""
    missing_headers = []
    for file_path in ROOT.rglob("*"):
        if not any(part.name in EXCLUDE_PATHS for part in file_path.parents):
            ext = file_path.suffix
            if ext in HEADERS and file_path.name not in EXCLUDE_FILES:
                if not check_header(file_path, HEADERS[ext]):
                    missing_headers.append(str(file_path))

    if missing_headers:
        exit(Exception("The following files are missing the required headers:\n" + "\n- ".join(missing_headers)))


if __name__ == "__main__":
    main()
