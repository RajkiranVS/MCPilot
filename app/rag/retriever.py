"""RAG Retriever — stubbed for production demo."""
from app.core.logging import get_logger
logger = get_logger(__name__)

class ToolRetriever:
    def __init__(self): pass
    async def retrieve(self, query, top_k=3):
        return []

tool_retriever = ToolRetriever()

def retrieve_tools(query, top_k=3):
    return []

def retrieve_best_tool(query):
    return None
