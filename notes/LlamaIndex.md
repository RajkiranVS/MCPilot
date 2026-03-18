# An introduction to LlamaIndex

## Where is LlamaIndex Used
The role of LlamaIndex comes during the Retrieval part of the RAG
   - It matches the user Query with the Vector Store and performs a symantic search
   - Retrieves the most relevant vectors
   - Send them to LLM for getting a Human Readable Response and return it back to the User
   - Before sending the response to the end user, it will be received by the LlamaIndex Framework, where accuracy is checked and post-processing is done.

## Role of LlamaIndex
* **Core Functions:** Bridges the gap between LLMs and external data
* **Capabilities:** Access Structured and Unstructured data dynamically
* **Advantage:** Extend LLMs beyond their _pre-trained Knowledge_

## Overview of Use Cases
* **AI-Powered Search:** Enables precise and contextual search systems.
* **Dynamic Q&A System:** Supports contextualized Question-Answering Applications
* **Knowledge Management:** Simplifies retrieval from complex unstructured data
* **Document Summarization:** Automates Summarizing Complex Datasets.

## Indexing
 - At a high-level, Indexes are built from Documents. They are used to build Query Engines and Chat Engines which enables question & answer and chat over your data.

 ### How Each Index Works?

 Internally, Data is organized into Node Objects which are etrieved using Retrieval model.

 * **Node:** Corresponds to a chunk of text from a Document. LlamaIndex takes in Document objects and internally parses/chunks them into Node objects.

 * **Response Synthesis:** Retrieval model pulls the most relevant node matching with the Query and generates a response.

 ### Different types of Indices

 #### Summary Index (Formerly List Index)
  The Summary index simply stores Nodes as a sequential chain.

   * **Querying** During query time, if no other query parameters are specified, LlamaIndex simply loads all Nodes in the list into our Response Synthesis module.

   The summary index does offer numerous ways of querying a summary index, from an embedding-based query which will fetch the top-k neighbors, or with the addition of a keyword filter.

#### Vector Store Index

The vector store index stores each Node and a corresponding embedding in a Vector Store.

* **Querying** Querying a vector store index involves fetching the top-k most similar Nodes, and passing those into our Response Synthesis module.

#### Tree Index
The tree index builds a hierarchical tree from a set of Nodes (which become leaf nodes in this tree).

* **Querying** Querying a tree index involves traversing from root nodes down to leaf nodes. By default, (child_branch_factor=1), a query chooses one child node given a parent node. If child_branch_factor=2, a query chooses two child nodes per level.

#### Keyword Table Index
The keyword table index extracts keywords from each Node and builds a mapping from each keyword to the corresponding Nodes of that keyword.

* **Querying** During query time, we extract relevant keywords from the query, and match those with pre-extracted Node keywords to fetch the corresponding Nodes. The extracted Nodes are passed to our Response Synthesis module.

#### Property Graph Index
The Property Graph Index works by first building a knowledge graph containing labelled nodes and relations. The construction of this graph is extremely customizable, ranging from letting the LLM extract whatever it wants, to extracting using a strict schema, to even implementing your own extraction modules.

Optionally, nodes can also be embedded for retrieval later.

You can also skip creation, and connect to an existing knowledge graph using an integration like Neo4j.

* **Querying** Querying a Property Graph Index is also highly flexible. Retrieval works by using several sub-retrievers and combining results. By default, keyword + synoymn expanasion is used, as well as vector retrieval (if your graph was embedded), to retrieve relevant triples.

You can also chose to include the source text in addition to the retrieved triples (unavailble for graphs created outside of LlamaIndex).

## MCPilot-Specific Patterns

### Creating Documents Programmatically
# No file loaders needed — create Documents from tool schema dicts directly
from llama_index.core import Document

doc = Document(
    text="echo: Echoes the input text back unchanged.",
    metadata={"server_id": "echo", "tool_name": "echo"}
)

### Retriever vs Query Engine
- Query Engine → synthesises a text answer → NOT what MCPilot needs
- Retriever → returns raw Node objects with metadata → USE THIS
  retriever = index.as_retriever(similarity_top_k=3)
  nodes = retriever.retrieve("find tools that read files")
  # nodes[0].metadata["server_id"] → "filesystem"
  # nodes[0].metadata["tool_name"] → "read_file"

### ChromaDB Integration
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
import chromadb

chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("mcp_tools")
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)




