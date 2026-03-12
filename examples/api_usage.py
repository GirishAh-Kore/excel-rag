"""
Example usage of the Google Drive Excel RAG API endpoints

This script demonstrates how to interact with the API programmatically.
"""

import requests
import time
import json
from typing import Optional


class RAGAPIClient:
    """Client for interacting with the RAG API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session_id: Optional[str] = None
    
    # ========================================================================
    # Authentication
    # ========================================================================
    
    def login(self) -> dict:
        """Initiate OAuth login flow"""
        response = self.session.post(f"{self.base_url}/api/v1/auth/login")
        response.raise_for_status()
        data = response.json()
        print(f"Please visit: {data['authorization_url']}")
        return data
    
    def check_auth_status(self) -> dict:
        """Check authentication status"""
        response = self.session.get(f"{self.base_url}/api/v1/auth/status")
        response.raise_for_status()
        return response.json()
    
    def logout(self) -> dict:
        """Logout and revoke access"""
        response = self.session.post(f"{self.base_url}/api/v1/auth/logout")
        response.raise_for_status()
        return response.json()
    
    # ========================================================================
    # Indexing
    # ========================================================================
    
    def start_full_indexing(
        self,
        folder_id: Optional[str] = None,
        file_filters: Optional[list] = None,
        force_reindex: bool = False
    ) -> dict:
        """Start full indexing"""
        payload = {
            "folder_id": folder_id,
            "file_filters": file_filters,
            "force_reindex": force_reindex
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/index/full",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def start_incremental_indexing(
        self,
        folder_id: Optional[str] = None,
        file_filters: Optional[list] = None
    ) -> dict:
        """Start incremental indexing"""
        payload = {
            "folder_id": folder_id,
            "file_filters": file_filters
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/index/incremental",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_indexing_status(self, job_id: str) -> dict:
        """Get indexing job status"""
        response = self.session.get(
            f"{self.base_url}/api/v1/index/status/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def get_indexing_report(self, job_id: str) -> dict:
        """Get indexing job report"""
        response = self.session.get(
            f"{self.base_url}/api/v1/index/report/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def pause_indexing(self, job_id: str) -> dict:
        """Pause indexing job"""
        response = self.session.post(
            f"{self.base_url}/api/v1/index/pause/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def resume_indexing(self, job_id: str) -> dict:
        """Resume indexing job"""
        response = self.session.post(
            f"{self.base_url}/api/v1/index/resume/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def stop_indexing(self, job_id: str) -> dict:
        """Stop indexing job"""
        response = self.session.post(
            f"{self.base_url}/api/v1/index/stop/{job_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_indexing(self, job_id: str, poll_interval: int = 2) -> dict:
        """Wait for indexing to complete"""
        print(f"Waiting for indexing job {job_id} to complete...")
        
        while True:
            status = self.get_indexing_status(job_id)
            progress = status['progress_percentage']
            current_file = status.get('current_file', 'N/A')
            
            print(f"Progress: {progress:.1f}% - Current file: {current_file}")
            
            if status['status'] in ['completed', 'failed', 'stopped']:
                print(f"Indexing {status['status']}")
                return self.get_indexing_report(job_id)
            
            time.sleep(poll_interval)
    
    # ========================================================================
    # Querying
    # ========================================================================
    
    def query(
        self,
        query: str,
        session_id: Optional[str] = None,
        language: Optional[str] = None
    ) -> dict:
        """Submit a query"""
        payload = {
            "query": query,
            "session_id": session_id or self.session_id,
            "language": language
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/query",
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # Store session ID for follow-up queries
        self.session_id = result['session_id']
        
        return result
    
    def clarify(self, session_id: str, selected_option_id: str) -> dict:
        """Respond to clarification question"""
        payload = {
            "session_id": session_id,
            "selected_option_id": selected_option_id
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/query/clarify",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_query_history(
        self,
        limit: int = 10,
        offset: int = 0,
        session_id: Optional[str] = None
    ) -> dict:
        """Get query history"""
        params = {"limit": limit, "offset": offset}
        if session_id:
            params["session_id"] = session_id
        
        response = self.session.get(
            f"{self.base_url}/api/v1/query/history",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def clear_query_history(self, session_id: Optional[str] = None) -> dict:
        """Clear query history"""
        params = {}
        if session_id:
            params["session_id"] = session_id
        
        response = self.session.delete(
            f"{self.base_url}/api/v1/query/history",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_session_context(self, session_id: str) -> dict:
        """Get session context"""
        response = self.session.get(
            f"{self.base_url}/api/v1/query/session/{session_id}"
        )
        response.raise_for_status()
        return response.json()
    
    def submit_feedback(
        self,
        query_id: str,
        helpful: bool,
        selected_file: Optional[str] = None,
        comments: Optional[str] = None
    ) -> dict:
        """Submit query feedback"""
        payload = {
            "query_id": query_id,
            "helpful": helpful,
            "selected_file": selected_file,
            "comments": comments
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/query/feedback",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    # ========================================================================
    # Utilities
    # ========================================================================
    
    def health_check(self) -> dict:
        """Check API health"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()


def example_authentication():
    """Example: Authentication flow"""
    print("\n" + "="*60)
    print("Example: Authentication")
    print("="*60)
    
    client = RAGAPIClient()
    
    # Check health
    health = client.health_check()
    print(f"\nAPI Status: {health['status']}")
    print(f"Version: {health['version']}")
    print(f"Environment: {health['environment']}")
    
    # Check authentication status
    status = client.check_auth_status()
    print(f"\nAuthenticated: {status['authenticated']}")
    
    if not status['authenticated']:
        print("\nTo authenticate:")
        print("1. Run: client.login()")
        print("2. Visit the authorization URL")
        print("3. Grant permissions")
        print("4. You'll be redirected back")


def example_indexing():
    """Example: Indexing workflow"""
    print("\n" + "="*60)
    print("Example: Indexing")
    print("="*60)
    
    client = RAGAPIClient()
    
    # Start full indexing
    print("\nStarting full indexing...")
    result = client.start_full_indexing(force_reindex=False)
    job_id = result['job_id']
    print(f"Job ID: {job_id}")
    print(f"Status: {result['status']}")
    
    # Wait for completion
    report = client.wait_for_indexing(job_id)
    
    # Print report
    print("\nIndexing Report:")
    print(f"  Files processed: {report['files_processed']}")
    print(f"  Files failed: {report['files_failed']}")
    print(f"  Files skipped: {report['files_skipped']}")
    print(f"  Sheets indexed: {report['sheets_indexed']}")
    print(f"  Embeddings generated: {report['embeddings_generated']}")
    print(f"  Duration: {report['duration_seconds']:.2f} seconds")


def example_querying():
    """Example: Query workflow"""
    print("\n" + "="*60)
    print("Example: Querying")
    print("="*60)
    
    client = RAGAPIClient()
    
    # Submit query
    print("\nSubmitting query...")
    result = client.query("What is the total expense in January 2024?")
    
    print(f"\nQuery processed in {result['processing_time_ms']:.2f}ms")
    print(f"Confidence: {result['confidence']:.1f}%")
    print(f"Session ID: {result['session_id']}")
    
    # Check if clarification is needed
    if result['requires_clarification']:
        print(f"\nClarification needed: {result['clarification_question']}")
        print("\nOptions:")
        for i, option in enumerate(result['clarification_options'], 1):
            print(f"  {i}. {option['description']} (confidence: {option['confidence']:.1f}%)")
        
        # In a real application, you would get user input here
        # selected = input("Select option: ")
        # clarified = client.clarify(result['session_id'], result['clarification_options'][int(selected)-1]['option_id'])
    else:
        print(f"\nAnswer: {result['answer']}")
        
        if result['sources']:
            print("\nSources:")
            for source in result['sources']:
                print(f"  - {source['citation_text']}")
    
    # Follow-up query (uses same session)
    print("\n" + "-"*60)
    print("Follow-up query...")
    result2 = client.query("What about February?")
    print(f"\nAnswer: {result2['answer']}")
    print(f"Confidence: {result2['confidence']:.1f}%")
    
    # Get query history
    print("\n" + "-"*60)
    print("Query history...")
    history = client.get_query_history(limit=5)
    print(f"\nTotal queries: {history['total']}")
    for item in history['queries']:
        print(f"  - {item['query']} (confidence: {item['confidence']:.1f}%)")


def example_session_management():
    """Example: Session management"""
    print("\n" + "="*60)
    print("Example: Session Management")
    print("="*60)
    
    client = RAGAPIClient()
    
    # Submit some queries
    result1 = client.query("What is the revenue in Q1?")
    session_id = result1['session_id']
    
    result2 = client.query("What about Q2?")
    
    # Get session context
    print(f"\nGetting session context for {session_id}...")
    context = client.get_session_context(session_id)
    
    print(f"\nSession created: {context['created_at']}")
    print(f"Last activity: {context['last_activity']}")
    print(f"Queries in session: {len(context['queries'])}")
    print(f"Selected files: {', '.join(context['selected_files'])}")
    
    # Clear history
    print("\nClearing session history...")
    result = client.clear_query_history(session_id=session_id)
    print(f"Cleared {result['queries_deleted']} queries")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("Google Drive Excel RAG API Examples")
    print("="*60)
    
    try:
        # Run examples
        example_authentication()
        # example_indexing()  # Uncomment when authenticated
        # example_querying()  # Uncomment when indexed
        # example_session_management()  # Uncomment when indexed
        
        print("\n" + "="*60)
        print("Examples completed!")
        print("="*60)
        
    except requests.exceptions.RequestException as e:
        print(f"\nAPI Error: {e}")
        if hasattr(e.response, 'json'):
            error = e.response.json()
            print(f"Error: {error.get('error')}")
            print(f"Message: {error.get('message')}")
            if 'correlation_id' in error:
                print(f"Correlation ID: {error['correlation_id']}")


if __name__ == "__main__":
    main()
