# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os

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
    ".ts": """/\*-------------------------------------
    Copyright: CEA-LIST/DIASI/SIALV/LVA
    Author : pixano@cea.fr
    License: CECILL-C
    -------------------------------------\*/
    \n""",
}

# Files to exclude
EXCLUDE_FILES = {
    "vite.config.ts",
    "vite-env.d.ts",
    "vite.env.d.ts",
    "ambient.d.ts",
    "$types.d.ts",
}


def check_header(file_path, header):
    """Check if the file contains the required header."""
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
        return content.startswith(header)


def main():
    missing_headers = []
    for root, _, files in os.walk("."):
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            if ext in HEADERS and file not in EXCLUDE_FILES:
                if not check_header(file_path, HEADERS[ext]):
                    missing_headers.append(file_path)

    if missing_headers:
        print("The following files miss the required license header :")
        for file in missing_headers:
            print(file)
        exit(1)
    else:
        print("All files include the required license header.")


if __name__ == "__main__":
    main()
