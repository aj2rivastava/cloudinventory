# parser.py
import json
import os

import json
import os

def parse_scoutsuite_file(file_path: str) -> dict:
    """
    Reads a 'new2.js' file containing
      scoutsuite_results = { "account_id": "...", ... };
    and returns a Python dict with the JSON data.
    """

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1) Remove the variable assignment (assumes "scoutsuite_results =")
    if "scoutsuite_results" in content:
        parts = content.split("=", 1)  # split once on '='
        if len(parts) == 2:
            # The second part is the actual JSON-like portion
            content = parts[1].strip()

    # 2) Remove trailing semicolon, if present
    if content.endswith(";"):
        content = content[:-1].strip()

    # 3) Fix possible trailing commas
    content = content.replace("},\n}", "}\n}")
    content = content.replace("},}", "}}")

    # 4) Parse it as JSON
    return json.loads(content)
