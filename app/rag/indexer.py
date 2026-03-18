"""
MCPilot — RAG Tool Indexer
Indexes all MCP tool schemas into ChromaDB via LlamaIndex.
Called at startup after MCP servers connect and tools are discovered.

Each tool becomes one Document:
  text    = "server_id.tool_name: description"
  metadata = {server_id, tool_name, input_schema}

This gives the retriever enough signal to match natural language
intent to the correct tool and server.
"""
import json
import chromadb
from llama_index.core import VectorStoreIndex, Document, StorageContext, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from app.core.logging import get_logger

logger = get_logger(__name__)

# Collection name in ChromaDB
COLLECTION_NAME = "mcp_tools"


def _build_document(tool: dict) -> Document:
    """
    Convert a tool schema dict into a LlamaIndex Document.
    Text is human-readable so embeddings capture semantic meaning.
    Metadata carries the routing info MCPManager needs.
    """
    server_id  = tool["server_id"]
    tool_name  = tool["name"]
    description = tool.get("description", "No description provided.")
    input_schema = tool.get("input_schema", {})

    # Build rich text for embedding — name + description + parameter names
    param_names = list(input_schema.get("properties", {}).keys())
    params_text = f"Parameters: {', '.join(param_names)}" if param_names else ""

    text = f"{server_id}.{tool_name}: {description} {params_text}".strip()

    return Document(
        text=text,
        metadata={
            "server_id":    server_id,
            "tool_name":    tool_name,
            "description":  description,
            "input_schema": json.dumps(input_schema),
        },
        # Exclude heavy metadata from embedding — only text is embedded
        excluded_embed_metadata_keys=["input_schema"],
        excluded_llm_metadata_keys=["input_schema"],
    )


class MCPToolIndexer:
    """
    Manages the LlamaIndex vector index of all MCP tool schemas.

    Lifecycle:
      1. build(tools)    → called at startup with all discovered tools
      2. refresh(tools)  → called when servers connect/disconnect
      3. Index persists in-memory ChromaDB for the process lifetime
         (Week 3: swap to persistent ChromaDB path)
    """

    def __init__(self):
        self._index: VectorStoreIndex | None = None
        self._chroma_client = chromadb.Client()  # in-memory
        self._collection = self._chroma_client.get_or_create_collection(
            COLLECTION_NAME
        )
        self._configure_settings()

    def _configure_settings(self):
        """
        Explicitly set local HuggingFace embedding model.
        Avoids requiring OpenAI API key.
        Model downloads ~130MB on first run, cached locally after.
        Week 3: swap to AWS Bedrock embeddings.
        """
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-small-en-v1.5"
        )
        Settings.chunk_size = 256
        Settings.chunk_overlap = 20
        Settings.llm = None  # No LLM needed — retriever only, not query engine

    def build(self, tools: list[dict]) -> None:
        """
        Build the index from scratch from a list of tool dicts.
        Each dict must have: server_id, name, description, input_schema.
        """
        if not tools:
            logger.warning("No tools to index — skipping RAG index build")
            return

        documents = [_build_document(t) for t in tools]

        vector_store = ChromaVectorStore(
            chroma_collection=self._collection
        )
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store
        )

        self._index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=False,
        )

        logger.info(
            f"RAG index built | tools={len(tools)} "
            f"servers={len(set(t['server_id'] for t in tools))}"
        )

    def refresh(self, tools: list[dict]) -> None:
        """
        Rebuild the index with a new tool list.
        Called when MCP servers connect or disconnect.
        """
        # Reset collection and rebuild
        self._chroma_client.delete_collection(COLLECTION_NAME)
        self._collection = self._chroma_client.get_or_create_collection(
            COLLECTION_NAME
        )
        self._index = None
        self.build(tools)
        logger.info("RAG index refreshed")

    @property
    def is_ready(self) -> bool:
        return self._index is not None

    @property
    def index(self) -> VectorStoreIndex | None:
        return self._index


# Module-level singleton
tool_indexer = MCPToolIndexer()