"""Secure token storage with encryption"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)


class TokenStorage:
    """Handles secure storage and retrieval of OAuth tokens with encryption"""
    
    def __init__(self, storage_path: str, encryption_key: str):
        """
        Initialize token storage with encryption
        
        Args:
            storage_path: Directory path for storing encrypted tokens
            encryption_key: Base64-encoded Fernet encryption key
            
        Raises:
            ValueError: If encryption key is invalid
        """
        self.storage_path = Path(storage_path)
        self.token_file = self.storage_path / "credentials.enc"
        
        # Validate and initialize encryption
        try:
            # If encryption key is provided as string, encode it
            if isinstance(encryption_key, str):
                # Check if it's already base64 encoded (Fernet key format)
                if len(encryption_key) == 44 and encryption_key.endswith('='):
                    key_bytes = encryption_key.encode()
                else:
                    # Generate Fernet key from provided string
                    # Pad or truncate to 32 bytes, then base64 encode
                    key_material = encryption_key.encode()
                    # Use first 32 bytes or pad with zeros
                    key_material = (key_material + b'\x00' * 32)[:32]
                    key_bytes = Fernet.generate_key()
                    # For consistency, derive from the provided key
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                    import base64
                    
                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=b'gdrive_rag_salt',  # Static salt for deterministic key
                        iterations=100000,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
                    key_bytes = key
            else:
                key_bytes = encryption_key
                
            self.cipher = Fernet(key_bytes)
            logger.info("Token storage initialized with encryption")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise ValueError(f"Invalid encryption key: {str(e)}")
        
        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def save_credentials(self, credentials: Credentials) -> bool:
        """
        Save OAuth credentials to encrypted file
        
        Args:
            credentials: Google OAuth2 credentials to save
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Convert credentials to dictionary
            creds_dict = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
                'expiry': credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            # Serialize to JSON
            json_data = json.dumps(creds_dict)
            
            # Encrypt data
            encrypted_data = self.cipher.encrypt(json_data.encode())
            
            # Write to file
            self.token_file.write_bytes(encrypted_data)
            
            # Set restrictive file permissions (owner read/write only)
            os.chmod(self.token_file, 0o600)
            
            logger.info("Credentials saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False
    
    def load_credentials(self) -> Optional[Credentials]:
        """
        Load and decrypt OAuth credentials from file
        
        Returns:
            Google OAuth2 credentials if found and valid, None otherwise
        """
        if not self.token_file.exists():
            logger.debug("No stored credentials found")
            return None
        
        try:
            # Read encrypted data
            encrypted_data = self.token_file.read_bytes()
            
            # Decrypt data
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # Parse JSON
            creds_dict = json.loads(decrypted_data.decode())
            
            # Convert expiry string back to datetime
            expiry = None
            if creds_dict.get('expiry'):
                expiry = datetime.fromisoformat(creds_dict['expiry'])
            
            # Create Credentials object
            credentials = Credentials(
                token=creds_dict['token'],
                refresh_token=creds_dict.get('refresh_token'),
                token_uri=creds_dict['token_uri'],
                client_id=creds_dict['client_id'],
                client_secret=creds_dict['client_secret'],
                scopes=creds_dict.get('scopes'),
            )
            
            # Set expiry manually (not in constructor)
            credentials.expiry = expiry
            
            logger.info("Credentials loaded successfully")
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None
    
    def delete_credentials(self) -> bool:
        """
        Delete stored credentials file
        
        Returns:
            True if deletion was successful or file didn't exist, False on error
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Credentials deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}")
            return False
    
    def credentials_exist(self) -> bool:
        """
        Check if credentials file exists
        
        Returns:
            True if credentials file exists, False otherwise
        """
        return self.token_file.exists()
    
    def update_token(self, credentials: Credentials) -> bool:
        """
        Update stored credentials (typically after token refresh)
        
        Args:
            credentials: Updated credentials to save
            
        Returns:
            True if update was successful, False otherwise
        """
        return self.save_credentials(credentials)


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key
    
    Returns:
        Base64-encoded encryption key suitable for TOKEN_ENCRYPTION_KEY
    """
    key = Fernet.generate_key()
    return key.decode()


# CLI utility for generating encryption keys
if __name__ == "__main__":
    print("Generating new encryption key for TOKEN_ENCRYPTION_KEY...")
    key = generate_encryption_key()
    print(f"\nGenerated key:\n{key}")
    print("\nAdd this to your .env file:")
    print(f"TOKEN_ENCRYPTION_KEY={key}")
