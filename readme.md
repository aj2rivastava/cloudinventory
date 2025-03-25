# Scout Suite CSPM Wrapper

This repository provides a **Cloud Security Posture Management (CSPM) wrapper** around [Scout Suite](https://github.com/nccgroup/ScoutSuite). It allows you to:

1. **Run** Scout Suite scans via API
2. **Parse** the JSON-like Scout Suite output
3. **Store** the raw data in MongoDB
4. **Refactor** the data into multiple collections
5. **Query** specific resources through REST APIs
6. **Monitor** scan status and progress

## Features

- **API-Driven Scanning**: Trigger Scout Suite scans via REST API
- **Status Tracking**: Monitor scan progress and status
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Connection Pooling**: Efficient MongoDB connection management
- **Error Recovery**: Automatic reconnection and error handling
- **Indexed Queries**: Optimized database performance
- **Resource-Specific Endpoints**: Easy access to AWS resources

## Prerequisites

- Python 3.8+
- MongoDB 4.4+
- AWS credentials configured
- Scout Suite installed

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd scout-suite-wrapper
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file with:
   ```
   MONGO_URI=mongodb://localhost:27017
   DB_NAME=aws_config
   MONGO_MAX_POOL_SIZE=100
   MONGO_MIN_POOL_SIZE=10
   MONGO_CONNECT_TIMEOUT_MS=5000
   MONGO_SERVER_SELECTION_TIMEOUT_MS=5000
   ```

## Usage

1. **Start the API server**:
   ```bash
   python app.py
   ```
   Or with gunicorn:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. **Run a Scout Suite scan**:
   ```bash
   curl -X POST http://localhost:5000/scout/run \
        -H "Content-Type: application/json" \
        -d '{
              "account_name": "myAccount",
              "profile_name": "default",
              "region": "us-east-1",
              "username": "user123"
            }'
   ```

3. **Check scan status**:
   ```bash
   curl http://localhost:5000/scout/status/user123
   ```

4. **Query resources**:
   ```bash
   # Get EC2 instances
   curl "http://localhost:5000/ec2/instances?account_id=YOUR_ACCOUNT_ID"

   # Get S3 buckets
   curl "http://localhost:5000/s3/buckets?account_id=YOUR_ACCOUNT_ID"

   # Get IAM users
   curl "http://localhost:5000/iam/users?account_id=YOUR_ACCOUNT_ID"
   ```

5. **Upload an existing report**:
   ```bash
   curl -X POST http://localhost:5000/reports/upload \
        -H "Content-Type: application/json" \
        -d '{
              "account_name": "myAccount",
              "report_path": "/path/to/new2.js",
              "timestamp": "20240215_123456"
            }'
   ```

## API Endpoints

### Scout Suite Operations

- `POST /scout/run`: Trigger a new Scout Suite scan
  ```json
  {
    "account_name": "myAccount",
    "profile_name": "default",
    "region": "us-east-1",
    "output_dir": "/path/to/output",
    "username": "user123"
  }
  ```

- `GET /scout/status/<username>`: Get scan status

### Resource Queries

- `GET /ec2/instances`: List all EC2 instances
- `GET /ec2/instances/<instance_id>`: Get specific EC2 instance
- `GET /s3/buckets`: List all S3 buckets
- `GET /iam/users`: List all IAM users

### Report Management

- `POST /reports/upload`: Upload and process an existing report
- `GET /reports/<account_name>`: List all reports for an account
- `GET /reports/<account_name>/latest`: Get the latest report for an account

## Development

1. **Code Style**:
   ```bash
   black .
   flake8
   mypy .
   ```

2. **Run Tests**:
   ```bash
   pytest
   ```

## Logging

Logs are stored in `/var/log/scout/`:
- `{username}.out.log.txt`: Standard output
- `{username}.err.log.txt`: Error output
- `{username}.status.txt`: Scan status
- `{username}.scout_pid`: Process ID

## Error Handling

The application includes comprehensive error handling:
- MongoDB connection failures
- Scout Suite execution errors
- Invalid input validation
- Resource not found scenarios

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
