# refactor.py
from typing import Dict, Any
from mongo_connect import db

def store_master_doc(data: Dict[str, Any], account_id: str) -> None:
    """
    Stores the raw data in a 'master' collection.
    Overwrites or upserts as needed.
    """
    # Use 'master' collection or a name of your choice
    master_collection = db["master"]

    # Upsert one doc per (account_id).
    # The raw data can be large, but usually fits in a single doc if not extremely huge.
    master_collection.find_one_and_update(
        {"account_id": account_id},
        {"$set": {"account_id": account_id, "raw_data": data}},
        upsert=True
    )

def refactor_and_store_resources(data: Dict[str, Any]) -> None:
    """
    Refactors the big dictionary from Scout Suite and stores resources
    into separate collections based on service or scope (global, regional, VPC).
    """
    if "account_id" not in data:
        raise KeyError("No 'account_id' found in data")
    account_id = data["account_id"]

    # Typically, Scout Suite puts stuff under data["services"]
    services = data.get("services", {})

    # ----------------------------------------------------------------
    # Example: store S3 buckets in a "s3_buckets" collection
    # ----------------------------------------------------------------
    s3_info = services.get("s3", {})
    # Buckets are generally global (not region-specific in the same sense)
    buckets = s3_info.get("buckets", {})
    for b_id, b_data in buckets.items():
        b_data["id"] = b_id
        b_data["account_id"] = account_id
        db["s3_buckets"].find_one_and_update(
            {"account_id": account_id, "id": b_id},
            {"$set": b_data},
            upsert=True
        )

    # ----------------------------------------------------------------
    # Example: store IAM resources (global)
    # ----------------------------------------------------------------
    iam_info = services.get("iam", {})
    # Could be users, roles, policies, groups, etc.
    # We'll do a quick example with "users".
    users = iam_info.get("users", {})
    for u_id, u_data in users.items():
        u_data["id"] = u_id
        u_data["account_id"] = account_id
        db["iam_users"].find_one_and_update(
            {"account_id": account_id, "id": u_id},
            {"$set": u_data},
            upsert=True
        )

    # ----------------------------------------------------------------
    # Example: store "EC2" resources (region -> vpcs -> instances, security_groups, etc.)
    # ----------------------------------------------------------------
    ec2_info = services.get("ec2", {})
    regions = ec2_info.get("regions", {})
    for region_name, region_data in regions.items():
        vpcs = region_data.get("vpcs", {})
        for vpc_id, vpc_data in vpcs.items():
            # 1) Instances
            instances = vpc_data.get("instances", {})
            for inst_id, inst_data in instances.items():
                doc = {
                    "account_id": account_id,
                    "region": region_name,
                    "vpc_id": vpc_id,
                    "instance_id": inst_id,
                    **inst_data
                }
                db["ec2_instances"].find_one_and_update(
                    {"account_id": account_id, "instance_id": inst_id},
                    {"$set": doc},
                    upsert=True
                )

            # 2) Security Groups
            sec_groups = vpc_data.get("security_groups", {})
            for sg_id, sg_data in sec_groups.items():
                doc = {
                    "account_id": account_id,
                    "region": region_name,
                    "vpc_id": vpc_id,
                    "sg_id": sg_id,
                    **sg_data
                }
                db["ec2_security_groups"].find_one_and_update(
                    {"account_id": account_id, "sg_id": sg_id},
                    {"$set": doc},
                    upsert=True
                )

    # ----------------------------------------------------------------
    # ... repeat for RDS, ELB, CloudTrail, CloudWatch, Route53, etc. ...
    #
    # Each type might have a different shape, e.g. route53 is "hosted_zones" -> ...
    # You can follow the same pattern:
    #   1) gather the dict with resources
    #   2) loop over each resource
    #   3) upsert into a dedicated collection
    #
    # This modular approach ensures each resource type is easy to query later.
    # ----------------------------------------------------------------

    print(f"Refactoring & storing resources for account_id={account_id} completed.")
