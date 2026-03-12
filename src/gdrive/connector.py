"""
Google Drive connector for listing, downloading, and monitoring Excel files.

This module provides functionality to interact with Google Drive API for:
- Recursive file listing with Excel filtering
- File download with streaming support
- Rate limiting and retry logic
- Change detection for incremental indexing
"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from functools import wraps

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io

from src.models.domain_models import FileMetadata, FileStatus
from src.auth.authentication_service import AuthenticationService

logger = logging.getLogger(__name__)


# Excel MIME types to filter
EXCEL_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.ms-excel.sheet.macroEnabled.12",  # .xlsm
}

# Excel file extensions
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}


def exponential_backoff_retry(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 32.0,
    exponential_base: float = 2.0
):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if e.resp.status in [403, 429, 500, 502, 503, 504]:
                        if attempt < max_retries:
                            logger.warning(
                                f"HTTP {e.resp.status} error in {func.__name__}, "
                                f"attempt {attempt + 1}/{max_retries}, "
                                f"retrying in {delay}s: {str(e)}"
                            )
                            time.sleep(delay)
                            delay = min(delay * exponential_base, max_delay)
                            continue
                    
                    # Non-retryable error or max retries reached
                    logger.error(f"HTTP error in {func.__name__}: {e}")
                    raise
                    
                except Exception as e:
                    last_exception = e
                    
                    # Network errors are retryable
                    if attempt < max_retries and _is_network_error(e):
                        logger.warning(
                            f"Network error in {func.__name__}, "
                            f"attempt {attempt + 1}/{max_retries}, "
                            f"retrying in {delay}s: {str(e)}"
                        )
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                        continue
                    
                    # Non-retryable error or max retries reached
                    logger.error(f"Error in {func.__name__}: {e}")
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def _is_network_error(exception: Exception) -> bool:
    """Check if exception is a network-related error."""
    error_types = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    return isinstance(exception, error_types)


class GoogleDriveConnector:
    """
    Connector for Google Drive API operations.
    
    Provides methods for listing files, downloading content, and monitoring changes.
    """
    
    def __init__(self, auth_service: AuthenticationService):
        """
        Initialize Google Drive connector.
        
        Args:
            auth_service: Authentication service for getting authenticated clients
        """
        self.auth_service = auth_service
        self._drive_service: Optional[Resource] = None
        self._page_token: Optional[str] = None
        
        logger.info("Google Drive connector initialized")
    
    def _get_drive_service(self) -> Resource:
        """
        Get or create authenticated Drive service.
        
        Returns:
            Authenticated Google Drive service
            
        Raises:
            ValueError: If authentication fails
        """
        if self._drive_service is None:
            self._drive_service = self.auth_service.get_authenticated_client(
                service_name="drive",
                version="v3"
            )
        return self._drive_service
    
    @exponential_backoff_retry(max_retries=5)
    def list_excel_files(
        self,
        folder_id: Optional[str] = None,
        recursive: bool = True
    ) -> List[FileMetadata]:
        """
        List all Excel files in Google Drive.
        
        Args:
            folder_id: Optional folder ID to start from (None for root)
            recursive: Whether to traverse folders recursively
            
        Returns:
            List of FileMetadata for Excel files
            
        Raises:
            HttpError: If API call fails
        """
        logger.info(f"Listing Excel files (folder_id={folder_id}, recursive={recursive})")
        
        excel_files = []
        folders_to_process = [(folder_id, "")]  # (folder_id, path)
        
        while folders_to_process:
            current_folder_id, current_path = folders_to_process.pop(0)
            
            # List files in current folder
            files, subfolders = self._list_folder_contents(current_folder_id)
            
            # Process Excel files
            for file_info in files:
                if self._is_excel_file(file_info):
                    file_metadata = self._create_file_metadata(file_info, current_path)
                    excel_files.append(file_metadata)
            
            # Add subfolders to process queue if recursive
            if recursive:
                for folder_info in subfolders:
                    folder_name = folder_info.get("name", "")
                    folder_path = f"{current_path}/{folder_name}" if current_path else f"/{folder_name}"
                    folders_to_process.append((folder_info["id"], folder_path))
        
        logger.info(f"Found {len(excel_files)} Excel files")
        return excel_files
    
    def _list_folder_contents(
        self,
        folder_id: Optional[str] = None
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        List contents of a specific folder.
        
        Args:
            folder_id: Folder ID (None for root)
            
        Returns:
            Tuple of (files, folders) as lists of file info dicts
        """
        drive_service = self._get_drive_service()
        
        # Build query
        if folder_id:
            query = f"'{folder_id}' in parents and trashed=false"
        else:
            query = "'root' in parents and trashed=false"
        
        files = []
        folders = []
        page_token = None
        
        while True:
            # List files with pagination
            response = drive_service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, md5Checksum, parents)',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            items = response.get('files', [])
            
            # Separate files and folders
            for item in items:
                if item.get('mimeType') == 'application/vnd.google-apps.folder':
                    folders.append(item)
                else:
                    files.append(item)
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        return files, folders
    
    def _is_excel_file(self, file_info: Dict[str, Any]) -> bool:
        """
        Check if file is an Excel file.
        
        Args:
            file_info: File information from Drive API
            
        Returns:
            True if file is Excel format
        """
        mime_type = file_info.get('mimeType', '')
        name = file_info.get('name', '')
        
        # Check MIME type
        if mime_type in EXCEL_MIME_TYPES:
            return True
        
        # Check file extension as fallback
        for ext in EXCEL_EXTENSIONS:
            if name.lower().endswith(ext):
                return True
        
        return False
    
    def _create_file_metadata(
        self,
        file_info: Dict[str, Any],
        folder_path: str
    ) -> FileMetadata:
        """
        Create FileMetadata from Drive API file info.
        
        Args:
            file_info: File information from Drive API
            folder_path: Path to folder containing file
            
        Returns:
            FileMetadata instance
        """
        file_name = file_info.get('name', 'Unknown')
        full_path = f"{folder_path}/{file_name}" if folder_path else f"/{file_name}"
        
        # Parse modified time
        modified_time_str = file_info.get('modifiedTime')
        if modified_time_str:
            # Remove 'Z' and parse
            modified_time = datetime.fromisoformat(modified_time_str.replace('Z', '+00:00'))
        else:
            modified_time = datetime.now()
        
        return FileMetadata(
            file_id=file_info['id'],
            name=file_name,
            path=full_path,
            mime_type=file_info.get('mimeType', ''),
            size=int(file_info.get('size', 0)),
            modified_time=modified_time,
            md5_checksum=file_info.get('md5Checksum', ''),
            status=FileStatus.PENDING
        )
    
    def get_file_metadata(self, file_id: str) -> FileMetadata:
        """
        Get metadata for a specific file.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            FileMetadata for the file
            
        Raises:
            HttpError: If file not found or API call fails
        """
        logger.debug(f"Getting metadata for file {file_id}")
        
        drive_service = self._get_drive_service()
        
        file_info = drive_service.files().get(
            fileId=file_id,
            fields='id, name, mimeType, size, modifiedTime, md5Checksum, parents'
        ).execute()
        
        # Get folder path
        folder_path = self._get_folder_path(file_info.get('parents', []))
        
        return self._create_file_metadata(file_info, folder_path)
    
    def _get_folder_path(self, parent_ids: List[str]) -> str:
        """
        Build folder path from parent IDs.
        
        Args:
            parent_ids: List of parent folder IDs
            
        Returns:
            Full folder path
        """
        if not parent_ids:
            return ""
        
        drive_service = self._get_drive_service()
        path_parts = []
        
        for parent_id in parent_ids:
            try:
                parent_info = drive_service.files().get(
                    fileId=parent_id,
                    fields='name, parents'
                ).execute()
                
                path_parts.insert(0, parent_info.get('name', ''))
                
                # Recursively get parent paths
                if parent_info.get('parents'):
                    parent_path = self._get_folder_path(parent_info['parents'])
                    if parent_path:
                        path_parts.insert(0, parent_path)
                        
            except HttpError as e:
                logger.warning(f"Could not get parent folder {parent_id}: {e}")
                continue
        
        return "/".join(path_parts) if path_parts else ""
    
    @exponential_backoff_retry(max_retries=5)
    def download_file(
        self,
        file_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bytes:
        """
        Download file content from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            progress_callback: Optional callback for progress updates (bytes_downloaded, total_bytes)
            
        Returns:
            File content as bytes
            
        Raises:
            HttpError: If file cannot be downloaded
        """
        logger.info(f"Downloading file {file_id}")
        
        drive_service = self._get_drive_service()
        
        # Create download request
        request = drive_service.files().get_media(fileId=file_id)
        
        # Download with streaming
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            
            if status and progress_callback:
                progress_callback(
                    int(status.resumable_progress),
                    int(status.total_size) if status.total_size else 0
                )
        
        content = file_buffer.getvalue()
        logger.info(f"Downloaded {len(content)} bytes for file {file_id}")
        
        return content
    
    def watch_changes(self, page_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Get changes since last check using Changes API.
        
        Args:
            page_token: Token from previous changes request (None for initial)
            
        Returns:
            Dict with 'changes' list and 'newStartPageToken'
        """
        logger.info(f"Watching for changes (page_token={page_token})")
        
        drive_service = self._get_drive_service()
        
        # Get start page token if not provided
        if page_token is None:
            response = drive_service.changes().getStartPageToken().execute()
            page_token = response.get('startPageToken')
            logger.info(f"Got initial page token: {page_token}")
            return {
                'changes': [],
                'newStartPageToken': page_token
            }
        
        # Get changes
        changes = []
        new_page_token = page_token
        
        while True:
            response = drive_service.changes().list(
                pageToken=new_page_token,
                spaces='drive',
                fields='nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, size, modifiedTime, md5Checksum, parents))',
                pageSize=100
            ).execute()
            
            changes.extend(response.get('changes', []))
            
            # Check for next page
            if 'nextPageToken' in response:
                new_page_token = response['nextPageToken']
            else:
                new_page_token = response.get('newStartPageToken')
                break
        
        # Filter for Excel files only
        excel_changes = []
        for change in changes:
            if change.get('removed'):
                # File was deleted
                excel_changes.append({
                    'type': 'deleted',
                    'file_id': change['fileId']
                })
            elif change.get('file'):
                file_info = change['file']
                if self._is_excel_file(file_info):
                    excel_changes.append({
                        'type': 'modified',
                        'file_info': file_info
                    })
        
        logger.info(f"Found {len(excel_changes)} Excel file changes")
        
        return {
            'changes': excel_changes,
            'newStartPageToken': new_page_token
        }
    
    def get_page_token(self) -> Optional[str]:
        """
        Get current page token for change tracking.
        
        Returns:
            Current page token or None
        """
        return self._page_token
    
    def set_page_token(self, page_token: str):
        """
        Set page token for change tracking.
        
        Args:
            page_token: Page token to store
        """
        self._page_token = page_token
        logger.debug(f"Page token updated: {page_token}")


# Factory function
def create_google_drive_connector(auth_service: AuthenticationService) -> GoogleDriveConnector:
    """
    Factory function to create Google Drive connector.
    
    Args:
        auth_service: Authentication service instance
        
    Returns:
        Configured GoogleDriveConnector instance
    """
    return GoogleDriveConnector(auth_service)
