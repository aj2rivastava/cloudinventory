# mongo_connect.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import os
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get MongoDB URI from environment variable or use default
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "aws_config")

# MongoDB connection settings
MAX_POOL_SIZE = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
MIN_POOL_SIZE = int(os.getenv("MONGO_MIN_POOL_SIZE", "10"))
CONNECT_TIMEOUT_MS = int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "5000"))
SERVER_SELECTION_TIMEOUT_MS = int(os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))

class MongoDBConnection:
    _instance: Optional['MongoDBConnection'] = None
    _client: Optional[MongoClient] = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBConnection, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._connect()

    def _connect(self):
        """Establish connection to MongoDB with retry logic"""
        try:
            self._client = MongoClient(
                MONGO_URI,
                maxPoolSize=MAX_POOL_SIZE,
                minPoolSize=MIN_POOL_SIZE,
                connectTimeoutMS=CONNECT_TIMEOUT_MS,
                serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS
            )
            
            # Test the connection
            self._client.admin.command('ping')
            
            self._db = self._client[DB_NAME]
            logger.info(f"Successfully connected to MongoDB at {MONGO_URI}")
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {str(e)}")
            raise

    def get_db(self):
        """Get database instance with connection check"""
        try:
            # Check if connection is still alive
            self._client.admin.command('ping')
            return self._db
        except Exception as e:
            logger.warning(f"MongoDB connection lost, attempting to reconnect: {str(e)}")
            self._connect()
            return self._db

    def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("MongoDB connection closed")

# Create global MongoDB connection instance
db_connection = MongoDBConnection()
db = db_connection.get_db()

def setup_indexes():
    """Set up MongoDB indexes for better query performance"""
    try:
        # EC2 instances indexes
        db.ec2_instances.create_index([("account_id", 1), ("instance_id", 1)], unique=True)
        db.ec2_instances.create_index([("region", 1)])
        db.ec2_instances.create_index([("vpc_id", 1)])

        # S3 buckets indexes
        db.s3_buckets.create_index([("account_id", 1)])
        db.s3_buckets.create_index([("name", 1)])

        # IAM users indexes
        db.iam_users.create_index([("account_id", 1)])
        db.iam_users.create_index([("username", 1)])

        # Master collection indexes
        db.master.create_index([("account_id", 1)], unique=True)

        logger.info("Successfully created MongoDB indexes")
    except OperationFailure as e:
        logger.error(f"Failed to create MongoDB indexes: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating MongoDB indexes: {str(e)}")
        raise

# Call this when your application starts
setup_indexes()
