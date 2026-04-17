"""RAG Indexer — stubbed for production demo (llama_index not required)."""
from app.core.logging import get_logger
logger = get_logger(__name__)

class MCPToolIndexer:
    def __init__(self): pass
    def build(self, tools):
        logger.info(f"RAG stub: skipping index build for {len(tools)} tools")
    async def build_index(self): pass
    async def index_tools(self, tools): pass

tool_indexer = MCPToolIndexer()
