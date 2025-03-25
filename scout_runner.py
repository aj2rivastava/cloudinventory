import subprocess
import os
import logging
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
from report_manager import report_manager
from typing import Optional

# Configure logging
SCOUT_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs", "scout")
os.makedirs(SCOUT_LOG_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SCOUT_REPORT_DIR = os.path.join(os.path.dirname(__file__), "scout2-report")

def _get_last_lines(file_path, num_lines=20):
    """Return the last `num_lines` lines from the given file_path."""
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "r") as f:
        lines = f.read().splitlines()
        return "\n".join(lines[-num_lines:])

def clear_aws_cached_credentials():
    """Removes cached AWS credentials used for STS AssumeRole after a scan."""
    cache_folder = os.path.join(os.path.expanduser('~'), '.aws', 'cli', 'cache')
    if not os.path.exists(cache_folder):
        return

    for file_name in os.listdir(cache_folder):
        file_path = os.path.join(cache_folder, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

def run_scout_suite(account_name, profile_name="default", region=None, timestamp=None, username=None):
    """
    Run Scout Suite scan and return path to results file
    
    Args:
        account_name: AWS account name to scan
        profile_name: Profile name (ruleset) for scanning
        region: AWS region to scan
        timestamp: Optional timestamp for report directory
        username: Username of whoever initiates this scan
    """
    # Get report directory path
    report_dir = report_manager.get_report_path(account_name, timestamp)

    # Prepare paths for logs/status
    stdout_log_path = os.path.join(SCOUT_LOG_DIR, f"{username or 'scout'}.out.log.txt")
    stderr_log_path = os.path.join(SCOUT_LOG_DIR, f"{username or 'scout'}.err.log.txt")
    status_log_path = os.path.join(SCOUT_LOG_DIR, f"{username or 'scout'}.status.txt")
    pid_file_path = os.path.join(SCOUT_LOG_DIR, f"{username or 'scout'}.scout_pid")

    # Build Scout Suite command
    cmd = [
        "scout", 
        "aws",
        "--profile", account_name,
        "--force",
        "--no-browser",
        "--report-dir", report_dir,
        "--ruleset", profile_name
    ]

    if region:
        cmd.extend(["--region", region])

    try:
        # Create log directory if it doesn't exist
        os.makedirs(SCOUT_LOG_DIR, exist_ok=True)

        # Open stdout/stderr logs in append mode
        with open(stdout_log_path, "a+") as scout_stdout, open(stderr_log_path, "a+") as scout_stderr:
            # Redirect this function's print statements to the log files
            with redirect_stdout(scout_stdout), redirect_stderr(scout_stderr):
                logger.info(f"Starting Scout scan for account '{account_name}' using profile '{profile_name}'")
                logger.info(f"Running command: {' '.join(cmd)}")

                # Write initial status and PID
                with open(status_log_path, "w+") as status_file:
                    status_file.write(f"running {account_name} {profile_name}")

                scout_process = subprocess.Popen(
                    cmd,
                    stdout=scout_stdout,
                    stderr=scout_stderr
                )
                with open(pid_file_path, "w") as pid_file:
                    pid_file.write(str(scout_process.pid))

                # Wait for the Scout process to finish
                scout_process.communicate()
                return_code = scout_process.poll()

                if return_code == 0:
                    # Success
                    with open(status_log_path, "w") as status_file:
                        status_file.write("completed")
                    logger.info("Scout scan completed successfully")
                else:
                    # Error
                    with open(status_log_path, "w") as status_file:
                        status_file.write("error")
                    logs = _get_last_lines(stderr_log_path, 20)
                    logger.error(f"Scout scan failed with return code {return_code}")
                    logger.error(f"Last 20 lines of error log:\n{logs}")
                    raise Exception(f"Scout scan failed: {logs}")

        # Scout Suite typically creates a 'scoutsuite-results' directory
        results_file = os.path.join(report_dir, "scoutsuite-results", "new2.js")
        
        if not os.path.exists(results_file):
            raise FileNotFoundError(f"Scout Suite results file not found at {results_file}")

        return results_file

    except Exception as e:
        logger.error(f"Error running Scout Suite: {str(e)}")
        raise
    finally:
        # Clear cached AWS credentials
        clear_aws_cached_credentials() 