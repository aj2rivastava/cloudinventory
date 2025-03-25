#!/usr/bin/env python3
import json
from pymongo import MongoClient
import sys
import os

def read_report_js(file_path):
    """
    Reads a Scout Suite 'report.js' file (which has JavaScript variable assignment),
    strips away the variable assignment, and returns a Python dictionary parsed from the
    JSON-like content.
    """
    if not os.path.exists(file_path):
        print(f"Error: The file {file_path} does not exist.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Look for the variable assignment "scoutsuite_results ="
    #    We remove everything up to the first "=" sign so the rest is the raw JSON data.
    if 'scoutsuite_results' in content:
        parts = content.split('=', 1)  # split only once
        if len(parts) == 2:
            # The second part should be the actual JSON-like object
            content = parts[1].strip()

    # 2. Remove any trailing semicolon or extra spaces
    if content.endswith(';'):
        content = content[:-1].strip()

    # 3. (Optional) If there's a trailing comma before the last brace, remove it.
    #    A simple replace that often helps if there's something like:
    #       "... },\n};"
    #    We'll attempt to remove only the trailing commas that break JSON.
    content = content.replace('},\n}', '}\n}')
    content = content.replace('},}', '}}')

    # 4. Now parse the JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        print("Error parsing JSON from the report.js file:", e)
        sys.exit(1)

    return data

def store_in_mongo(data):
    """
    Given a Python dictionary `data` from the Scout Suite report,
    use the 'account_id' field as the MongoDB database name and
    insert the entire dictionary into a 'scoutsuite' collection (or any name you prefer).
    """
    # 1. Extract the account_id from the data
    #    Adjust the key if it's different in your actual JSON.
    if "account_id" not in data:
        print("Error: 'account_id' key not found in the parsed data.")
        sys.exit(1)

    account_id = data["account_id"]
    print(f"Account ID found: {account_id}")

    # 2. Connect to MongoDB (assumes localhost:27017 with no auth)
    client = MongoClient("mongodb://localhost:27017")

    # 3. Use the 'account_id' as the database name
    db = client[account_id]

    # 4. Name the collection (here we're calling it 'scoutsuite', but you can choose)
    collection = db["scoutsuite"]

    # 5. Insert the data
    #    If it's a dictionary, use insert_one. If you expect a list at the top level, use insert_many.
    if isinstance(data, dict):
        result = collection.insert_one(data)
        print(f"Inserted 1 document into DB '{account_id}', collection 'scoutsuite'.")
        print(f"New document _id: {result.inserted_id}")
    elif isinstance(data, list):
        result = collection.insert_many(data)
        print(f"Inserted {len(result.inserted_ids)} documents into DB '{account_id}', collection 'scoutsuite'.")
    else:
        print("Data is neither a dictionary nor a list. Insertion skipped.")

    # 6. Close the connection
    client.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python store_scoutsuite.py <path_to_report_js_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    data = read_report_js(file_path)
    store_in_mongo(data)
    print("Done.")


def find_resource_by_key(data, resource_name):
    """
    Recursively search for a dictionary key matching `resource_name`.
    Returns the sub-dictionary/value if found, else None.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            # Check if the current key matches the resource name
            if k == resource_name:
                return v  # Return its value (sub-dict or otherwise)

            # Otherwise, keep searching deeper
            found = find_resource_by_key(v, resource_name)
            if found is not None:
                return found

    elif isinstance(data, list):
        # Search each element in the list
        for item in data:
            found = find_resource_by_key(item, resource_name)
            if found is not None:
                return found

    return None



if __name__ == "__main__":
    main()
