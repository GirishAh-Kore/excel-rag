# Authentication Module

This module provides secure OAuth 2.0 authentication for Google Drive access with automatic token refresh and encrypted token storage.

## Features

- **OAuth 2.0 Flow**: Complete implementation of Google OAuth 2.0 authorization flow
- **Secure Token Storage**: Encrypted storage of access and refresh tokens using Fernet encryption
- **Automatic Token Refresh**: Automatic refresh of expired tokens with 5-minute buffer
- **CSRF Protection**: State parameter validation to prevent CSRF attacks
- **Authenticated Client Factory**: Easy creation of authenticated Google API clients

## Components

### 1. OAuthFlow (`oauth_flow.py`)

Handles the OAuth 2.0 authorization flow with Google.

**Key Methods:**
- `get_authorization_url()`: Generate authorization URL with CSRF protection
- `handle_callback()`: Exchange authorization code for tokens

**Example:**
```python
from src.auth import OAuthFlow
from src.config import AppConfig

config = AppConfig.from_env()
oauth = OAuthFlow(config.google_drive)

# Get authorization URL
auth_url, state = oauth.get_authorization_url()
print(f"Visit: {auth_url}")

# After user authorizes, handle callback
credentials = oauth.handle_callback(
    authorization_code="code_from_callback",
    state=state
)
```

### 2. TokenStorage (`token_storage.py`)

Provides secure encrypted storage for OAuth tokens.

**Key Methods:**
- `save_credentials()`: Save encrypted credentials to file
- `load_credentials()`: Load and decrypt credentials from file
- `delete_credentials()`: Remove stored credentials
- `credentials_exist()`: Check if credentials are stored

**Security Features:**
- Fernet symmetric encryption
- PBKDF2 key derivation from user-provided key
- Restrictive file permissions (0600)
- Automatic key generation utility

**Example:**
```python
from src.auth import TokenStorage

storage = TokenStorage(
    storage_path="./tokens",
    encryption_key="your-32-char-key"
)

# Save credentials
storage.save_credentials(credentials)

# Load credentials
credentials = storage.load_credentials()
```

### 3. TokenRefreshManager (`token_refresh.py`)

Manages automatic token refresh with expiration checking.

**Key Methods:**
- `is_token_expired()`: Check if token needs refresh (5-minute buffer)
- `refresh_token()`: Refresh access token using refresh token
- `ensure_valid_token()`: Ensure token is valid, refresh if needed
- `get_valid_credentials()`: Load and validate credentials from storage

**Example:**
```python
from src.auth import TokenRefreshManager, TokenStorage

storage = TokenStorage("./tokens", "encryption-key")
refresh_manager = TokenRefreshManager(storage)

# Get valid credentials (auto-refresh if needed)
credentials = refresh_manager.get_valid_credentials()
```

### 4. AuthenticationService (`authentication_service.py`)

Main service that orchestrates OAuth flow, token storage, and refresh.

**Key Methods:**
- `initiate_oauth_flow()`: Start OAuth authorization
- `handle_oauth_callback()`: Complete OAuth flow and save tokens
- `is_authenticated()`: Check authentication status
- `get_authenticated_client()`: Get authenticated Google API client
- `revoke_access()`: Revoke tokens and delete credentials

**Example:**
```python
from src.auth import AuthenticationService
from src.config import AppConfig

config = AppConfig.from_env()
auth_service = AuthenticationService(config.google_drive)

# Check if authenticated
if auth_service.is_authenticated():
    # Get authenticated Drive client
    drive = auth_service.get_authenticated_client()
    
    # Use the client
    results = drive.files().list(pageSize=10).execute()
else:
    # Start OAuth flow
    auth_url, state = auth_service.initiate_oauth_flow()
    print(f"Please visit: {auth_url}")
```

## Configuration

Required environment variables (in `.env`):

```bash
# Google OAuth credentials (from Google Cloud Console)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback

# OAuth scopes (comma-separated)
GOOGLE_SCOPES=https://www.googleapis.com/auth/drive.readonly

# Token storage
TOKEN_STORAGE_PATH=./tokens
TOKEN_ENCRYPTION_KEY=your_32_character_encryption_key
```

### Generating Encryption Key

Generate a secure encryption key:

```bash
# Using Python
python -m src.auth.token_storage

# Or using the example script
python examples/auth_usage.py genkey
```

## Usage Examples

### Complete Authentication Flow

```python
from src.config import AppConfig
from src.auth import AuthenticationService

# Load config
config = AppConfig.from_env()
auth_service = AuthenticationService(config.google_drive)

# Step 1: Check if already authenticated
if auth_service.is_authenticated():
    print("Already authenticated!")
    drive = auth_service.get_authenticated_client()
else:
    # Step 2: Initiate OAuth flow
    auth_url, state = auth_service.initiate_oauth_flow()
    print(f"Visit: {auth_url}")
    
    # Step 3: After user authorizes, handle callback
    # (In a web app, this would be in your callback endpoint)
    code = input("Enter authorization code: ")
    success = auth_service.handle_oauth_callback(code, state, state)
    
    if success:
        print("Authentication successful!")
        drive = auth_service.get_authenticated_client()
```

### Automatic Token Refresh

Token refresh happens automatically when you call `get_authenticated_client()`:

```python
# This will automatically refresh the token if it's expired
drive = auth_service.get_authenticated_client()

# Token is guaranteed to be valid (or an exception is raised)
files = drive.files().list().execute()
```

### Manual Token Refresh

```python
# Manually trigger refresh
if auth_service.refresh_credentials():
    print("Token refreshed successfully")
else:
    print("Refresh failed - re-authentication needed")
```

### Revoke Access

```python
# Revoke access and delete stored credentials
if auth_service.revoke_access():
    print("Access revoked successfully")
```

### Check Authentication Status

```python
from src.auth import AuthenticationStatus

status = auth_service.get_authentication_status()

if status == AuthenticationStatus.AUTHENTICATED:
    print("Authenticated and ready")
elif status == AuthenticationStatus.NOT_AUTHENTICATED:
    print("Not authenticated - need to complete OAuth flow")
elif status == AuthenticationStatus.REFRESH_FAILED:
    print("Token refresh failed - need to re-authenticate")
```

## Error Handling

The authentication module handles various error scenarios:

### OAuth Errors

```python
try:
    auth_url, state = auth_service.initiate_oauth_flow()
except ValueError as e:
    print(f"OAuth configuration error: {e}")
```

### Token Refresh Errors

```python
try:
    drive = auth_service.get_authenticated_client()
except ValueError as e:
    print(f"Authentication error: {e}")
    # User needs to re-authenticate
    auth_url, state = auth_service.initiate_oauth_flow()
```

### CSRF Protection

```python
try:
    auth_service.handle_oauth_callback(code, state, expected_state)
except ValueError as e:
    print(f"CSRF validation failed: {e}")
```

## Security Considerations

1. **Encryption Key**: Store `TOKEN_ENCRYPTION_KEY` securely
   - Use environment variables
   - Never commit to version control
   - Use different keys for different environments

2. **Token Storage**: Tokens are stored with restrictive permissions (0600)
   - Only the owner can read/write
   - Encrypted with Fernet (AES-128)

3. **CSRF Protection**: State parameter prevents CSRF attacks
   - Random 32-byte state generated per flow
   - Validated during callback

4. **Token Refresh**: Automatic refresh with 5-minute buffer
   - Prevents expired token errors
   - Seamless user experience

5. **Scope Limitation**: Request only necessary scopes
   - Use `drive.readonly` for read-only access
   - Minimize permissions

## Testing

Run the example script to test authentication:

```bash
# Test authentication flow
python examples/auth_usage.py auth

# Test token refresh
python examples/auth_usage.py refresh

# Revoke access
python examples/auth_usage.py revoke

# Generate encryption key
python examples/auth_usage.py genkey
```

## Integration with Google Drive API

Once authenticated, use the client to access Google Drive:

```python
# Get authenticated client
drive = auth_service.get_authenticated_client()

# List files
results = drive.files().list(
    pageSize=10,
    fields="files(id, name, mimeType)"
).execute()

files = results.get('files', [])
for file in files:
    print(f"{file['name']} ({file['id']})")

# Download file
file_id = "your_file_id"
request = drive.files().get_media(fileId=file_id)
content = request.execute()
```

## Troubleshooting

### "Invalid encryption key" error

Generate a new key:
```bash
python examples/auth_usage.py genkey
```

### "Not authenticated" error

Complete the OAuth flow:
```bash
python examples/auth_usage.py auth
```

### "Token refresh failed" error

Re-authenticate:
```bash
python examples/auth_usage.py revoke
python examples/auth_usage.py auth
```

### "Invalid state parameter" error

This indicates a CSRF attack or session issue. Start a new OAuth flow.

## Requirements

- `google-auth-oauthlib>=1.2.0`
- `google-api-python-client>=2.116.0`
- `cryptography>=42.0.0`
- `python-dotenv>=1.0.0`

## References

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [Cryptography Library](https://cryptography.io/)
