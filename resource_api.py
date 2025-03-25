from fastapi import FastAPI, HTTPException, Query
from pymongo import MongoClient
from typing import Optional, List, Dict

app = FastAPI()

# -------------------------------------------------------------------
# 1. HELPER: MongoDB retrieval
# -------------------------------------------------------------------
def get_scoutsuite_document(account_id: str):
    """
    Connect to MongoDB and retrieve the single large Scout Suite
    document from the 'scoutsuite' collection in the given `account_id` database.
    """
    client = MongoClient("mongodb://localhost:27017")
    db = client[account_id]         # e.g., '430150006394'
    collection = db["scoutsuite"]   # e.g., 'scoutsuite'

    # We assume there's only one main doc. If there's more than one, adapt as needed.
    doc = collection.find_one({})
    client.close()
    return doc

# -------------------------------------------------------------------
# 2. HELPER: Gather all EC2 Instances
# -------------------------------------------------------------------
def get_ec2_instances(doc: dict) -> List[Dict]:
    """
    Looks for EC2 instance data in doc["services"]["ec2"]["regions"][REGION]["vpcs"][VPC]["instances"][INSTANCE].
    Returns a list of {"instance_id": ..., "metadata": {...}} objects.
    """
    services = doc.get("services", {})
    ec2_data = services.get("ec2", {})
    regions = ec2_data.get("regions", {})

    results = []
    for region_id, region_data in regions.items():
        # Within each region, we have "vpcs"
        vpcs = region_data.get("vpcs", {})
        for vpc_id, vpc_data in vpcs.items():
            instances = vpc_data.get("instances", {})
            for instance_id, instance_info in instances.items():
                # Build a list of (instance_id, metadata)
                results.append({
                    "instance_id": instance_id,
                    "metadata": instance_info
                })
    return results

# -------------------------------------------------------------------
# 3. ENDPOINT: GET /category
# -------------------------------------------------------------------
@app.get("/category")
def get_resources_by_category(
    account_id: str = Query(..., description="Account ID (database name)"),
    category_name: str = Query(..., description="Service/category name, e.g. 'ec2' or 'cloudtrail'")
):
    """
    If category_name='ec2', returns a list of all EC2 instance IDs
    (and their metadata) from the Scout Suite document.
    Otherwise, returns everything under doc["services"][category_name].
    """
    doc = get_scoutsuite_document(account_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Scout Suite document found in this database.")

    category_name_lower = category_name.lower()

    # 1. Check if "ec2" -> do special logic
    if category_name_lower == "ec2":
        ec2_instances = get_ec2_instances(doc)
        # Return them
        return {
            "category_name": "ec2",
            "instances": ec2_instances
        }

    # 2. Otherwise, handle it the "general" way
    services = doc.get("services", {})
    category_data = services.get(category_name_lower)
    if category_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category_name}' not found in 'services'."
        )

    return {
        "category_name": category_name_lower,
        "metadata": category_data
    }

# -------------------------------------------------------------------
# 4. ENDPOINT: GET /resource (from previous example)
# -------------------------------------------------------------------
def find_resource_by_key(data, resource_name):
    """
    Recursively search for a dictionary key matching `resource_name`.
    Returns the sub-dictionary/value if found, else None.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if k == resource_name:
                return v
            found = find_resource_by_key(v, resource_name)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_resource_by_key(item, resource_name)
            if found is not None:
                return found
    return None

@app.get("/resource")
def get_resource_metadata(
    account_id: str = Query(..., description="Account ID (database name)"),
    resource_name: str = Query(..., description="The name of the resource you're looking for")
):
    """
    Returns all metadata about a given resource (by name) from the
    Scout Suite doc identified by the account_id.
    """
    doc = get_scoutsuite_document(account_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No Scout Suite document found in this database.")

    resource_data = find_resource_by_key(doc, resource_name)
    if resource_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Resource '{resource_name}' not found in the Scout Suite data."
        )
    return {"resource_name": resource_name, "metadata": resource_data}