# Google Drive Connector

This module provides functionality to interact with Google Drive API for the Excel RAG system.

## Features

- **File Listing**: Recursively list all Excel files across folders
- **File Download**: Download file content with streaming support
- **Rate Limiting**: Automatic exponential backoff retry logic
- **Change Detection**: Monitor file changes for incremental indexing
- **Error Handling**: Robust error handling for API failures

## Usage

### Basic File Listing

```python
from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service
from src.gdrive import create_google_drive_connector

# Load configuration
config = AppConfig.from_env()

# Create authentication service
auth_service = create_authentication_service(config.google_drive)

# Create Google Drive connector
connector = create_google_drive_connector(auth_service)

# List all Excel files recursively
excel_files = connector.list_excel_files(recursive=True)

for file in excel_files:
    print(f"File: {file.name}")
    print(f"  Path: {file.path}")
    print(f"  Size: {file.size} bytes")
    print(f"  Modified: {file.modified_time}")
    print(f"  MD5: {file.md5_checksum}")
```

### Download File

```python
# Download file content
file_id = "your-file-id"

def progress_callback(downloaded, total):
    if total > 0:
        percent = (downloaded / total) * 100
        print(f"Downloaded: {percent:.1f}%")

content = connector.download_file(file_id, progress_callback=progress_callback)

# Save to disk
with open("downloaded_file.xlsx", "wb") as f:
    f.write(content)
```

### Monitor Changes

```python
# Get initial page token
result = connector.watch_changes()
page_token = result['newStartPageToken']

# Store page token for next check
connector.set_page_token(page_token)

# Later, check for changes
result = connector.watch_changes(page_token=page_token)

for change in result['changes']:
    if change['type'] == 'deleted':
        print(f"File deleted: {change['file_id']}")
    elif change['type'] == 'modified':
        file_info = change['file_info']
        print(f"File modified: {file_info['name']}")

# Update page token
connector.set_page_token(result['newStartPageToken'])
```

### Get File Metadata

```python
# Get metadata for specific file
file_id = "your-file-id"
metadata = connector.get_file_metadata(file_id)

print(f"File: {metadata.name}")
print(f"Path: {metadata.path}")
print(f"Size: {metadata.size}")
print(f"Modified: {metadata.modified_time}")
```

## Error Handling

The connector includes automatic retry logic with exponential backoff for:

- Rate limit errors (403, 429)
- Server errors (500, 502, 503, 504)
- Network errors (connection, timeout)

Maximum 5 retry attempts with delays from 1s to 32s.

```python
from googleapiclient.errors import HttpError

try:
    files = connector.list_excel_files()
except HttpError as e:
    if e.resp.status == 404:
        print("File or folder not found")
    elif e.resp.status == 403:
        print("Permission denied or rate limit exceeded")
    else:
        print(f"API error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Excel File Detection

The connector automatically filters for Excel files based on:

- **MIME types**:
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (.xlsx)
  - `application/vnd.ms-excel` (.xls)
  - `application/vnd.ms-excel.sheet.macroEnabled.12` (.xlsm)

- **File extensions** (fallback):
  - `.xlsx`
  - `.xls`
  - `.xlsm`

## Rate Limiting

The connector respects Google Drive API rate limits:

- Uses exponential backoff for rate limit errors
- Automatically retries failed requests
- Logs all retry attempts for debugging

## Change Detection

The Changes API allows efficient incremental indexing:

1. Get initial page token
2. Store page token
3. Periodically check for changes using stored token
4. Process only changed files
5. Update page token for next check

This approach is much more efficient than re-scanning all files.

## Dependencies

- `google-api-python-client`: Google Drive API client
- `google-auth`: Authentication
- `src.auth`: Authentication service
- `src.models`: Domain models

## Configuration

Required environment variables:

```bash
# Google OAuth credentials
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
GOOGLE_SCOPES=https://www.googleapis.com/auth/drive.readonly

# Token storage
TOKEN_STORAGE_PATH=./tokens
TOKEN_ENCRYPTION_KEY=your-32-char-encryption-key
```

## Logging

The connector uses Python's logging module:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or configure specific logger
logger = logging.getLogger('src.gdrive.connector')
logger.setLevel(logging.DEBUG)
```

## Testing

See `examples/gdrive_usage.py` for complete usage examples.

## Notes

- All file operations require valid authentication
- The connector automatically refreshes expired tokens
- Folder paths are built recursively from parent IDs
- Pagination is handled automatically (100 files per page)
- Streaming is used for large file downloads
