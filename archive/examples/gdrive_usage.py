"""
Example usage of Google Drive connector.

This script demonstrates how to use the Google Drive connector to:
- List Excel files
- Download files
- Monitor changes
- Handle errors
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AppConfig
from src.auth.authentication_service import create_authentication_service
from src.gdrive import create_google_drive_connector
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def list_files_example():
    """Example: List all Excel files in Google Drive."""
    print("\n" + "="*60)
    print("Example 1: List Excel Files")
    print("="*60)
    
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Create authentication service
        auth_service = create_authentication_service(config.google_drive)
        
        # Check authentication
        if not auth_service.is_authenticated():
            print("❌ Not authenticated. Please run authentication first.")
            print("   Run: python examples/auth_usage.py")
            return
        
        # Create Google Drive connector
        connector = create_google_drive_connector(auth_service)
        
        # List all Excel files recursively
        print("\n📂 Listing Excel files...")
        excel_files = connector.list_excel_files(recursive=True)
        
        print(f"\n✅ Found {len(excel_files)} Excel files:\n")
        
        for i, file in enumerate(excel_files, 1):
            print(f"{i}. {file.name}")
            print(f"   Path: {file.path}")
            print(f"   Size: {file.size:,} bytes")
            print(f"   Modified: {file.modified_time}")
            print(f"   MD5: {file.md5_checksum}")
            print(f"   Status: {file.status.value}")
            print()
        
        return excel_files
        
    except HttpError as e:
        print(f"\n❌ Google Drive API error: {e}")
        if e.resp.status == 403:
            print("   This might be a permission or rate limit issue.")
        elif e.resp.status == 404:
            print("   File or folder not found.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error listing files")


def download_file_example(file_id: str):
    """
    Example: Download a file from Google Drive.
    
    Args:
        file_id: Google Drive file ID to download
    """
    print("\n" + "="*60)
    print("Example 2: Download File")
    print("="*60)
    
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Create authentication service
        auth_service = create_authentication_service(config.google_drive)
        
        # Create Google Drive connector
        connector = create_google_drive_connector(auth_service)
        
        # Get file metadata first
        print(f"\n📄 Getting metadata for file {file_id}...")
        metadata = connector.get_file_metadata(file_id)
        
        print(f"\nFile: {metadata.name}")
        print(f"Size: {metadata.size:,} bytes")
        print(f"Path: {metadata.path}")
        
        # Download with progress callback
        print(f"\n⬇️  Downloading...")
        
        def progress_callback(downloaded, total):
            if total > 0:
                percent = (downloaded / total) * 100
                bar_length = 40
                filled = int(bar_length * downloaded / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r[{bar}] {percent:.1f}% ({downloaded:,}/{total:,} bytes)", end='')
        
        content = connector.download_file(file_id, progress_callback=progress_callback)
        print()  # New line after progress
        
        # Save to disk
        output_path = Path("downloads") / metadata.name
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, "wb") as f:
            f.write(content)
        
        print(f"\n✅ Downloaded to: {output_path}")
        print(f"   Size: {len(content):,} bytes")
        
    except HttpError as e:
        print(f"\n❌ Google Drive API error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error downloading file")


def monitor_changes_example():
    """Example: Monitor file changes for incremental indexing."""
    print("\n" + "="*60)
    print("Example 3: Monitor Changes")
    print("="*60)
    
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Create authentication service
        auth_service = create_authentication_service(config.google_drive)
        
        # Create Google Drive connector
        connector = create_google_drive_connector(auth_service)
        
        # Get initial page token
        print("\n🔄 Getting initial page token...")
        result = connector.watch_changes()
        page_token = result['newStartPageToken']
        
        print(f"✅ Initial page token: {page_token}")
        print(f"   Changes: {len(result['changes'])}")
        
        # Store page token
        connector.set_page_token(page_token)
        
        print("\n💡 Page token stored. In a real application:")
        print("   1. Store this token in database")
        print("   2. Periodically check for changes using this token")
        print("   3. Process only changed files")
        print("   4. Update token after each check")
        
        # Simulate checking for changes
        print("\n🔍 Checking for changes since last token...")
        result = connector.watch_changes(page_token=page_token)
        
        print(f"\n✅ Found {len(result['changes'])} changes:")
        
        if result['changes']:
            for change in result['changes']:
                if change['type'] == 'deleted':
                    print(f"   ❌ Deleted: {change['file_id']}")
                elif change['type'] == 'modified':
                    file_info = change['file_info']
                    print(f"   ✏️  Modified: {file_info['name']}")
        else:
            print("   No changes detected")
        
        print(f"\n📌 New page token: {result['newStartPageToken']}")
        
    except HttpError as e:
        print(f"\n❌ Google Drive API error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error monitoring changes")


def error_handling_example():
    """Example: Error handling and retry logic."""
    print("\n" + "="*60)
    print("Example 4: Error Handling")
    print("="*60)
    
    try:
        # Load configuration
        config = AppConfig.from_env()
        
        # Create authentication service
        auth_service = create_authentication_service(config.google_drive)
        
        # Create Google Drive connector
        connector = create_google_drive_connector(auth_service)
        
        # Try to get metadata for non-existent file
        print("\n🧪 Testing error handling with invalid file ID...")
        
        try:
            metadata = connector.get_file_metadata("invalid-file-id-12345")
            print(f"File: {metadata.name}")
        except HttpError as e:
            if e.resp.status == 404:
                print("✅ Correctly handled 404 error: File not found")
            else:
                print(f"❌ Unexpected error: {e}")
        
        print("\n💡 The connector includes automatic retry logic for:")
        print("   - Rate limit errors (403, 429)")
        print("   - Server errors (500, 502, 503, 504)")
        print("   - Network errors (connection, timeout)")
        print("   - Maximum 5 retries with exponential backoff (1s to 32s)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Error in error handling example")


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Google Drive Connector Examples")
    print("="*60)
    
    # Example 1: List files
    excel_files = list_files_example()
    
    # Example 2: Download file (if files found)
    if excel_files and len(excel_files) > 0:
        print("\n💡 To download a file, uncomment the download example")
        print(f"   Example file ID: {excel_files[0].file_id}")
        # Uncomment to test download:
        # download_file_example(excel_files[0].file_id)
    
    # Example 3: Monitor changes
    monitor_changes_example()
    
    # Example 4: Error handling
    error_handling_example()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
