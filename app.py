# app.py
import os
import logging
from flask import Flask, request, jsonify, render_template, flash, redirect, url_for
from parser import parse_scoutsuite_file
from refactor import store_master_doc, refactor_and_store_resources
from mongo_connect import db
from scout_runner import run_scout_suite
from report_manager import report_manager
from datetime import datetime

# Configure logging
SCOUT_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs", "scout")
os.makedirs(SCOUT_LOG_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for flash messages

# AWS Regions for the form
AWS_REGIONS = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-west-3',
    'eu-central-1', 'eu-north-1',
    'ap-south-1', 'ap-southeast-1', 'ap-southeast-2',
    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'sa-east-1', 'ca-central-1'
]

# -------------------------------------------------------------------
# UI Routes
# -------------------------------------------------------------------
@app.route("/")
def index():
    """Home page with dashboard overview"""
    account_id = request.args.get("account_id")
    accounts = list(db.master.distinct("account_id"))
    
    if account_id:
        ec2_count = db.ec2_instances.count_documents({"account_id": account_id})
        s3_count = db.s3_buckets.count_documents({"account_id": account_id})
        iam_count = db.iam_users.count_documents({"account_id": account_id})
    else:
        ec2_count = s3_count = iam_count = 0
        if accounts:
            account_id = accounts[0]

    # Get recent scans
    recent_scans = []
    for doc in db.master.find().sort("timestamp", -1).limit(5):
        status_file = os.path.join(SCOUT_LOG_DIR, f"{doc.get('username', 'unknown')}.status.txt")
        status = "completed"
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                status = f.read().strip()
        
        recent_scans.append({
            "account_name": doc.get("account_name", "Unknown"),
            "timestamp": doc.get("timestamp", "Unknown"),
            "status": status,
            "status_color": {
                "completed": "success",
                "running": "info",
                "error": "danger",
                "stopped": "warning"
            }.get(status, "secondary")
        })

    return render_template(
        "index.html",
        accounts=[{"id": id, "name": id} for id in accounts],
        selected_account=account_id,
        ec2_count=ec2_count,
        s3_count=s3_count,
        iam_count=iam_count,
        recent_scans=recent_scans
    )

@app.route("/run-scan")
def run_scan_page():
    """Page to run a new Scout Suite scan"""
    accounts = list(db.master.distinct("account_id"))
    return render_template(
        "run_scan.html",
        accounts=[{"id": id, "name": id} for id in accounts],
        aws_regions=AWS_REGIONS
    )

@app.route("/ec2")
def view_ec2():
    """Page to view EC2 instances"""
    account_id = request.args.get("account_id")
    accounts = list(db.master.distinct("account_id"))
    
    instances = []
    if account_id:
        instances = list(db.ec2_instances.find({"account_id": account_id}, {"_id": False}))
    
    return render_template(
        "ec2.html",
        accounts=[{"id": id, "name": id} for id in accounts],
        instances=instances,
        selected_account=account_id
    )

@app.route("/s3")
def view_s3():
    """Page to view S3 buckets"""
    account_id = request.args.get("account_id")
    accounts = list(db.master.distinct("account_id"))
    
    buckets = []
    if account_id:
        buckets = list(db.s3_buckets.find({"account_id": account_id}, {"_id": False}))
    
    return render_template(
        "s3.html",
        accounts=[{"id": id, "name": id} for id in accounts],
        buckets=buckets,
        selected_account=account_id
    )

@app.route("/iam")
def view_iam():
    """Page to view IAM users"""
    account_id = request.args.get("account_id")
    accounts = list(db.master.distinct("account_id"))
    
    users = []
    if account_id:
        users = list(db.iam_users.find({"account_id": account_id}, {"_id": False}))
    
    return render_template(
        "iam.html",
        accounts=[{"id": id, "name": id} for id in accounts],
        users=users,
        selected_account=account_id
    )

# -------------------------------------------------------------------
# 1. Endpoint to process a new Scout Suite report
# -------------------------------------------------------------------
@app.route("/scan", methods=["POST"])
def scan():
    """
    Expects JSON body:
      {
        "file_path": "/path/to/new2.js"
      }
    1. Parse the file.
    2. Store raw doc in 'master'.
    3. Refactor into separate collections.
    """
    data = request.get_json()
    if not data or "file_path" not in data:
        return jsonify({"error": "Missing 'file_path' in request JSON"}), 400

    file_path = data["file_path"]
    if not os.path.isfile(file_path):
        return jsonify({"error": f"File not found: {file_path}"}), 400

    try:
        parsed_data = parse_scoutsuite_file(file_path)
    except Exception as e:
        logger.error(f"Failed to parse file: {str(e)}")
        return jsonify({"error": f"Failed to parse file: {str(e)}"}), 500

    account_id = parsed_data.get("account_id", None)
    if not account_id:
        return jsonify({"error": "No 'account_id' found in parsed data"}), 400

    try:
        # 1) Store raw doc in 'master'
        store_master_doc(parsed_data, account_id)

        # 2) Refactor data into resource-specific collections
        refactor_and_store_resources(parsed_data)

        logger.info(f"Successfully processed scan data for account {account_id}")
        return jsonify({"message": "Scan data processed successfully", "account_id": account_id})
    except Exception as e:
        logger.error(f"Failed to store/refactor data: {str(e)}")
        return jsonify({"error": f"Failed to process data: {str(e)}"}), 500

# -------------------------------------------------------------------
# 2. Endpoint to run Scout Suite scan
# -------------------------------------------------------------------
@app.route("/scout/run", methods=["POST"])
def run_scout():
    """
    Trigger a Scout Suite scan and process results
    Expected JSON body:
    {
        "account_name": "myAccount",
        "profile_name": "default",
        "region": "us-east-1",  # optional
        "output_dir": "/path/to/output",  # optional
        "username": "user123"  # optional
    }
    """
    data = request.get_json()
    if not data or "account_name" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        logger.info(f"Starting Scout Suite scan for account {data['account_name']}")
        
        # Run Scout Suite scan
        output_path = run_scout_suite(
            account_name=data["account_name"],
            profile_name=data.get("profile_name", "default"),
            region=data.get("region"),
            output_dir=data.get("output_dir"),
            username=data.get("username")
        )

        # Parse the results
        parsed_data = parse_scoutsuite_file(output_path)
        
        # Store in MongoDB
        account_id = parsed_data.get("account_id")
        if not account_id:
            logger.error("No account_id found in scan results")
            return jsonify({"error": "No account_id found in scan results"}), 500

        store_master_doc(parsed_data, account_id)
        refactor_and_store_resources(parsed_data)

        logger.info(f"Successfully completed Scout Suite scan for account {account_id}")
        return jsonify({
            "message": "Scout Suite scan completed and processed",
            "account_id": account_id
        })

    except Exception as e:
        logger.error(f"Failed to run Scout Suite scan: {str(e)}")
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# 3. Endpoint to get scan status
# -------------------------------------------------------------------
@app.route("/scout/status/<username>", methods=["GET"])
def get_scan_status(username):
    """
    Get the status of a Scout Suite scan for a given username
    """
    status_file = os.path.join(SCOUT_LOG_DIR, f"{username}.status.txt")
    if not os.path.exists(status_file):
        return jsonify({"error": f"No scan status found for user {username}"}), 404

    try:
        with open(status_file, "r") as f:
            status = f.read().strip()
        return jsonify({"status": status})
    except Exception as e:
        logger.error(f"Failed to read scan status: {str(e)}")
        return jsonify({"error": f"Failed to read scan status: {str(e)}"}), 500

# -------------------------------------------------------------------
# 4. Example endpoint: get all EC2 instances for an account
# -------------------------------------------------------------------
@app.route("/ec2/instances", methods=["GET"])
def get_ec2_instances():
    """
    Query param: ?account_id=430150006394
    Returns all EC2 instances from the 'ec2_instances' collection
    for the given account.
    """
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "Missing account_id query parameter"}), 400

    cursor = db["ec2_instances"].find({"account_id": account_id}, {"_id": False})
    instances = list(cursor)
    return jsonify(instances)

# -------------------------------------------------------------------
# 5. Example endpoint: get one EC2 instance by instance_id
# -------------------------------------------------------------------
@app.route("/ec2/instances/<instance_id>", methods=["GET"])
def get_ec2_instance(instance_id):
    """
    Query param: ?account_id=430150006394
    Return details of one instance by instance_id.
    """
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "Missing account_id query parameter"}), 400

    doc = db["ec2_instances"].find_one(
        {"account_id": account_id, "instance_id": instance_id},
        {"_id": False}
    )
    if not doc:
        return jsonify({"error": f"Instance {instance_id} not found"}), 404

    return jsonify(doc)

# -------------------------------------------------------------------
# 6. Example endpoint: get all S3 buckets
# -------------------------------------------------------------------
@app.route("/s3/buckets", methods=["GET"])
def get_s3_buckets():
    """
    Query param: ?account_id=430150006394
    Return all buckets from the 's3_buckets' collection for that account.
    """
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "Missing account_id query parameter"}), 400

    cursor = db["s3_buckets"].find({"account_id": account_id}, {"_id": False})
    buckets = list(cursor)
    return jsonify(buckets)

# -------------------------------------------------------------------
# 7. Example: get all IAM users
# -------------------------------------------------------------------
@app.route("/iam/users", methods=["GET"])
def get_iam_users():
    """
    Query param: ?account_id=430150006394
    Return all IAM users from 'iam_users' collection.
    """
    account_id = request.args.get("account_id")
    if not account_id:
        return jsonify({"error": "Missing account_id query parameter"}), 400

    cursor = db["iam_users"].find({"account_id": account_id}, {"_id": False})
    users = list(cursor)
    return jsonify(users)

# -------------------------------------------------------------------
# 8. Endpoint to upload and process an existing report
# -------------------------------------------------------------------
@app.route("/reports/upload", methods=["POST"])
def upload_report():
    """
    Upload and process an existing Scout Suite report
    Expected JSON body:
    {
        "account_name": "myAccount",
        "report_path": "/path/to/new2.js",
        "timestamp": "20240215_123456"  # optional
    }
    """
    data = request.get_json()
    if not data or "account_name" not in data or "report_path" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    report_path = data["report_path"]
    if not os.path.isfile(report_path):
        return jsonify({"error": f"Report file not found: {report_path}"}), 400

    try:
        # Parse the report
        parsed_data = parse_scoutsuite_file(report_path)
        
        # Store in MongoDB
        account_id = parsed_data.get("account_id")
        if not account_id:
            logger.error("No account_id found in report")
            return jsonify({"error": "No account_id found in report"}), 500

        store_master_doc(parsed_data, account_id)
        refactor_and_store_resources(parsed_data)

        # Copy report to managed directory if timestamp is provided
        if "timestamp" in data:
            target_dir = report_manager.get_report_path(data["account_name"], data["timestamp"])
            target_path = os.path.join(target_dir, "scoutsuite-results", "new2.js")
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(report_path, "rb") as src, open(target_path, "wb") as dst:
                dst.write(src.read())
            logger.info(f"Copied report to managed directory: {target_path}")

        logger.info(f"Successfully processed report for account {account_id}")
        return jsonify({
            "message": "Report processed successfully",
            "account_id": account_id
        })

    except Exception as e:
        logger.error(f"Failed to process report: {str(e)}")
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# 9. Endpoint to list reports for an account
# -------------------------------------------------------------------
@app.route("/reports/<account_name>", methods=["GET"])
def list_reports(account_name):
    """
    List all reports available for an account
    """
    try:
        reports = report_manager.list_account_reports(account_name)
        return jsonify({
            "account_name": account_name,
            "reports": reports
        })
    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# 10. Endpoint to get latest report for an account
# -------------------------------------------------------------------
@app.route("/reports/<account_name>/latest", methods=["GET"])
def get_latest_report(account_name):
    """
    Get the latest report for an account
    """
    try:
        report_path = report_manager.get_latest_report(account_name)
        if not report_path:
            return jsonify({"error": f"No reports found for account {account_name}"}), 404

        # Parse and return the report data
        parsed_data = parse_scoutsuite_file(report_path)
        return jsonify(parsed_data)
    except Exception as e:
        logger.error(f"Failed to get latest report: {str(e)}")
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# View specific report
# -------------------------------------------------------------------
@app.route("/reports/<account_name>/<timestamp>")
def view_report(account_name, timestamp):
    """
    View a specific report for an account at a given timestamp
    """
    try:
        # Get the master document from MongoDB
        master_doc = db.master.find_one({"account_name": account_name, "timestamp": timestamp}, {"_id": False})
        if not master_doc:
            flash("Report not found", "danger")
            return redirect(url_for("index"))

        # Get resource counts from respective collections
        account_id = master_doc.get("account_id")
        if not account_id:
            flash("Invalid report data: missing account ID", "danger")
            return redirect(url_for("index"))

        # Get EC2 instances
        ec2_instances = list(db.ec2_instances.find({"account_id": account_id}, {"_id": False}))
        running_instances = [i for i in ec2_instances if i.get("state") == "running"]

        # Get S3 buckets
        s3_buckets = list(db.s3_buckets.find({"account_id": account_id}, {"_id": False}))
        public_buckets = [b for b in s3_buckets if b.get("public_access")]

        # Get IAM users
        iam_users = list(db.iam_users.find({"account_id": account_id}, {"_id": False}))
        mfa_users = [u for u in iam_users if u.get("mfa_devices")]

        # Get findings from master document
        findings = master_doc.get("findings", {})

        report_data = {
            "account_id": account_id,
            "services": {
                "ec2": {"instances": ec2_instances},
                "s3": {"buckets": s3_buckets},
                "iam": {"users": iam_users}
            },
            "findings": findings
        }
        
        return render_template(
            "report.html",
            account_name=account_name,
            timestamp=timestamp,
            report_data=report_data,
            ec2_count=len(ec2_instances),
            running_ec2_count=len(running_instances),
            s3_count=len(s3_buckets),
            public_s3_count=len(public_buckets),
            iam_count=len(iam_users),
            mfa_user_count=len(mfa_users)
        )
    except Exception as e:
        logger.error(f"Failed to view report: {str(e)}")
        flash(f"Error viewing report: {str(e)}", "danger")
        return redirect(url_for("index"))

# -------------------------------------------------------------------
# Run the Flask app
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Ensure log directory exists
    os.makedirs(SCOUT_LOG_DIR, exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5002)
