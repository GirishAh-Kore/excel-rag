"""
API Routes Package

This package contains modular API route definitions for the Excel Query Pipeline.
Each module defines routes for a specific domain area.

Modules:
- chunks: Chunk visibility and debugging endpoints (Requirements 13.1-13.6)
- query: Query pipeline endpoints (Requirements 14.1-14.6, 16.3, 17.3)
- batch: Batch query and template endpoints (Requirements 24.1, 24.5, 25.1-25.4)
- export: Export and webhook endpoints (Requirements 26.3, 28.2, 28.5)
- intelligence: Intelligence feature endpoints (Requirements 37.1, 38.5, 42.4)
"""

from src.api.routes.batch import router as batch_router
from src.api.routes.chunks import router as chunks_router
from src.api.routes.export import router as export_router
from src.api.routes.intelligence import router as intelligence_router
from src.api.routes.query import router as query_router

__all__ = [
    "chunks_router",
    "query_router",
    "batch_router",
    "export_router",
    "intelligence_router",
]
