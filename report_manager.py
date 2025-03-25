import os
import logging
from datetime import datetime
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
SCOUT_REPORT_DIR = os.path.join(BASE_REPORT_DIR, "scout")
TEMP_REPORT_DIR = os.path.join(BASE_REPORT_DIR, "temp")

class ReportManager:
    def __init__(self):
        # Create necessary directories
        os.makedirs(SCOUT_REPORT_DIR, exist_ok=True)
        os.makedirs(TEMP_REPORT_DIR, exist_ok=True)

    def get_report_path(self, account_name: str, timestamp: Optional[str] = None) -> str:
        """
        Generate a report path for a given account and timestamp.
        If timestamp is not provided, current timestamp will be used.
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create account-specific directory
        account_dir = os.path.join(SCOUT_REPORT_DIR, account_name)
        os.makedirs(account_dir, exist_ok=True)
        
        # Create timestamp-specific directory
        report_dir = os.path.join(account_dir, timestamp)
        os.makedirs(report_dir, exist_ok=True)
        
        return report_dir

    def get_temp_path(self, prefix: str = "scout") -> str:
        """Generate a temporary directory path for processing"""
        return os.path.join(TEMP_REPORT_DIR, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    def cleanup_temp_files(self, temp_dir: str):
        """Clean up temporary files after processing"""
        try:
            if os.path.exists(temp_dir):
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

    def get_latest_report(self, account_name: str) -> Optional[str]:
        """Get the path to the latest report for an account"""
        account_dir = os.path.join(SCOUT_REPORT_DIR, account_name)
        if not os.path.exists(account_dir):
            return None

        # Get all timestamp directories and sort them
        timestamps = [d for d in os.listdir(account_dir) if os.path.isdir(os.path.join(account_dir, d))]
        if not timestamps:
            return None

        latest_timestamp = sorted(timestamps)[-1]
        report_path = os.path.join(account_dir, latest_timestamp, "scoutsuite-results", "new2.js")
        
        return report_path if os.path.exists(report_path) else None

    def list_account_reports(self, account_name: str) -> list:
        """List all reports available for an account"""
        account_dir = os.path.join(SCOUT_REPORT_DIR, account_name)
        if not os.path.exists(account_dir):
            return []

        reports = []
        for timestamp in os.listdir(account_dir):
            report_path = os.path.join(account_dir, timestamp, "scoutsuite-results", "new2.js")
            if os.path.exists(report_path):
                reports.append({
                    "timestamp": timestamp,
                    "path": report_path,
                    "created_at": datetime.strptime(timestamp, "%Y%m%d_%H%M%S").isoformat()
                })
        
        return sorted(reports, key=lambda x: x["timestamp"], reverse=True)

# Create global report manager instance
report_manager = ReportManager() 