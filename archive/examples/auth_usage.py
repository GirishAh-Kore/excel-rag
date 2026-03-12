"""Example usage of the authentication service"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import AppConfig
from src.auth import AuthenticationService, AuthenticationStatus


def example_authentication_flow():
    """Demonstrate the complete authentication flow"""
    
    print("=" * 60)
    print("Google Drive Authentication Example")
    print("=" * 60)
    
    # Load configuration
    print("\n1. Loading configuration...")
    try:
        config = AppConfig.from_env()
        print(f"   ✓ Configuration loaded")
        print(f"   - Client ID: {config.google_drive.client_id[:20]}...")
        print(f"   - Redirect URI: {config.google_drive.redirect_uri}")
        print(f"   - Scopes: {', '.join(config.google_drive.scopes)}")
    except Exception as e:
        print(f"   ✗ Failed to load configuration: {e}")
        return
    
    # Create authentication service
    print("\n2. Creating authentication service...")
    try:
        auth_service = AuthenticationService(config.google_drive)
        print("   ✓ Authentication service created")
    except Exception as e:
        print(f"   ✗ Failed to create authentication service: {e}")
        return
    
    # Check current authentication status
    print("\n3. Checking authentication status...")
    status = auth_service.get_authentication_status()
    print(f"   Status: {status.value}")
    
    if status == AuthenticationStatus.AUTHENTICATED:
        print("   ✓ Already authenticated!")
        
        # Try to get authenticated client
        print("\n4. Creating authenticated Google Drive client...")
        try:
            drive_client = auth_service.get_authenticated_client()
            print("   ✓ Authenticated client created successfully")
            
            # Test the client with a simple API call
            print("\n5. Testing API access...")
            try:
                about = drive_client.about().get(fields="user").execute()
                user_email = about.get('user', {}).get('emailAddress', 'Unknown')
                print(f"   ✓ Successfully connected as: {user_email}")
            except Exception as e:
                print(f"   ✗ API test failed: {e}")
                
        except Exception as e:
            print(f"   ✗ Failed to create client: {e}")
    
    else:
        print("   Not authenticated. Starting OAuth flow...")
        
        # Initiate OAuth flow
        print("\n4. Initiating OAuth flow...")
        try:
            auth_url, state = auth_service.initiate_oauth_flow()
            print("   ✓ Authorization URL generated")
            print(f"\n   Please visit this URL to authorize:")
            print(f"   {auth_url}")
            print(f"\n   State parameter (for CSRF protection): {state}")
            print("\n   After authorization, you'll be redirected to the callback URL")
            print("   with an authorization code. Use that code with handle_oauth_callback()")
            
        except Exception as e:
            print(f"   ✗ Failed to initiate OAuth flow: {e}")


def example_token_refresh():
    """Demonstrate automatic token refresh"""
    
    print("\n" + "=" * 60)
    print("Token Refresh Example")
    print("=" * 60)
    
    # Load configuration
    config = AppConfig.from_env()
    auth_service = AuthenticationService(config.google_drive)
    
    # Check if authenticated
    if not auth_service.is_authenticated():
        print("\n✗ Not authenticated. Please complete OAuth flow first.")
        return
    
    print("\n✓ Authenticated")
    
    # Get credentials
    credentials = auth_service.get_credentials()
    if credentials:
        print(f"\nCurrent token info:")
        print(f"  - Token: {credentials.token[:20]}...")
        print(f"  - Expiry: {credentials.expiry}")
        print(f"  - Has refresh token: {credentials.refresh_token is not None}")
        
        # Check if token needs refresh
        from src.auth import TokenRefreshManager
        refresh_manager = TokenRefreshManager(auth_service.token_storage)
        
        if refresh_manager.is_token_expired(credentials):
            print("\n⚠ Token is expired or expiring soon")
            print("  Attempting automatic refresh...")
            
            if auth_service.refresh_credentials():
                print("  ✓ Token refreshed successfully")
            else:
                print("  ✗ Token refresh failed")
        else:
            time_left = refresh_manager.get_time_until_expiry(credentials)
            print(f"\n✓ Token is valid for {time_left:.0f} more seconds")


def example_revoke_access():
    """Demonstrate access revocation"""
    
    print("\n" + "=" * 60)
    print("Revoke Access Example")
    print("=" * 60)
    
    # Load configuration
    config = AppConfig.from_env()
    auth_service = AuthenticationService(config.google_drive)
    
    # Check if authenticated
    if not auth_service.is_authenticated():
        print("\n✗ Not authenticated. Nothing to revoke.")
        return
    
    print("\n⚠ This will revoke access and delete stored credentials.")
    response = input("Are you sure? (yes/no): ")
    
    if response.lower() == 'yes':
        print("\nRevoking access...")
        if auth_service.revoke_access():
            print("✓ Access revoked successfully")
            print("  - Token revoked with Google")
            print("  - Local credentials deleted")
        else:
            print("✗ Failed to revoke access")
    else:
        print("Cancelled.")


def example_generate_encryption_key():
    """Generate a new encryption key"""
    
    print("\n" + "=" * 60)
    print("Generate Encryption Key")
    print("=" * 60)
    
    from src.auth import generate_encryption_key
    
    key = generate_encryption_key()
    print(f"\nGenerated encryption key:")
    print(f"{key}")
    print(f"\nAdd this to your .env file:")
    print(f"TOKEN_ENCRYPTION_KEY={key}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Authentication examples")
    parser.add_argument(
        'action',
        choices=['auth', 'refresh', 'revoke', 'genkey'],
        help='Action to perform'
    )
    
    args = parser.parse_args()
    
    if args.action == 'auth':
        example_authentication_flow()
    elif args.action == 'refresh':
        example_token_refresh()
    elif args.action == 'revoke':
        example_revoke_access()
    elif args.action == 'genkey':
        example_generate_encryption_key()
