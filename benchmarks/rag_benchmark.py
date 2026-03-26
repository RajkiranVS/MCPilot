"""
MCPilot — RAG Tool Discovery Benchmark
SAT-002: Measures semantic retrieval precision and recall
across 20 test queries against 4 MCP tool schemas.

Metrics:
  Precision@1  — correct tool is the top result
  Precision@3  — correct tool appears in top 3 results
  MRR          — Mean Reciprocal Rank (1/rank of first correct result)
  Avg Score    — mean similarity score of correct matches

Run: python benchmarks/rag_benchmark.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag.indexer import MCPToolIndexer
from app.rag.retriever import retrieve_tools
from app.rag import retriever as r

# ── Tool corpus — mirrors real MCPilot server setup ───────────────────────────
TOOLS = [
    {
        "server_id":    "filesystem",
        "name":         "read_file",
        "description":  "Read the complete contents of a file from the file system. Handles different file encodings.",
        "input_schema": {
            "properties": {"path": {"type": "string", "description": "Path to the file to read"}},
            "required":   ["path"],
        },
    },
    {
        "server_id":    "filesystem",
        "name":         "write_file",
        "description":  "Write content to a file on the file system. Creates the file if it does not exist.",
        "input_schema": {
            "properties": {
                "path":    {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "server_id":    "fetch",
        "name":         "fetch",
        "description":  "Fetch a URL from the internet and return its content as text or HTML.",
        "input_schema": {
            "properties": {
                "url":            {"type": "string",  "description": "URL to fetch"},
                "max_length":     {"type": "integer", "description": "Maximum response length"},
                "raw":            {"type": "boolean", "description": "Return raw HTML instead of text"},
            },
            "required": ["url"],
        },
    },
    {
        "server_id":    "echo",
        "name":         "echo",
        "description":  "Echo the input text back unchanged. Useful for testing and debugging.",
        "input_schema": {
            "properties": {"text": {"type": "string", "description": "Text to echo back"}},
            "required":   ["text"],
        },
    },
]

# ── 20 benchmark queries with ground truth ────────────────────────────────────
# Format: (query, expected_server_id, expected_tool_name, category)
QUERIES = [
    # File reading — 5 queries
    ("read a file from disk",                        "filesystem", "read_file",  "file_read"),
    ("get the contents of a text file",              "filesystem", "read_file",  "file_read"),
    ("open and read a document",                     "filesystem", "read_file",  "file_read"),
    ("load file contents into memory",               "filesystem", "read_file",  "file_read"),
    ("retrieve data stored in a local file",         "filesystem", "read_file",  "file_read"),

    # File writing — 5 queries
    ("write text to a file",                         "filesystem", "write_file", "file_write"),
    ("save content to disk",                         "filesystem", "write_file", "file_write"),
    ("create a new file with some content",          "filesystem", "write_file", "file_write"),
    ("store output to a file path",                  "filesystem", "write_file", "file_write"),
    ("write data to a local file on the filesystem", "filesystem", "write_file", "file_write"),

    # Web fetch — 5 queries
    ("fetch content from a URL",                     "fetch",      "fetch",      "web_fetch"),
    ("get the HTML of a webpage",                    "fetch",      "fetch",      "web_fetch"),
    ("download a web page",                          "fetch",      "fetch",      "web_fetch"),
    ("retrieve content from the internet",           "fetch",      "fetch",      "web_fetch"),
    ("make an HTTP request to a website",            "fetch",      "fetch",      "web_fetch"),

    # Echo / testing — 5 queries
    ("echo some text back to me",                    "echo",       "echo",       "echo"),
    ("repeat my input unchanged",                    "echo",       "echo",       "echo"),
    ("test the connection by echoing a message",     "echo",       "echo",       "echo"),
    ("send a test string and get it back",           "echo",       "echo",       "echo"),
    ("mirror my input for debugging purposes",       "echo",       "echo",       "echo"),
]


def run_benchmark():
    # ── Build index ───────────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("MCPilot RAG Tool Discovery Benchmark — SAT-002")
    print("="*65)
    print(f"\nIndexing {len(TOOLS)} tools across {len(set(t['server_id'] for t in TOOLS))} servers...")

    indexer = MCPToolIndexer()
    indexer.build(TOOLS)
    r.tool_indexer = indexer
    print("Index built ✓\n")

    # ── Run queries ───────────────────────────────────────────────────────────
    results = []
    category_stats = {}

    for query, exp_server, exp_tool, category in QUERIES:
        candidates = retrieve_tools(query, top_k=3)

        # Find rank of correct tool
        rank = None
        correct_score = 0.0
        for i, c in enumerate(candidates, 1):
            if c["server_id"] == exp_server and c["tool_name"] == exp_tool:
                rank = i
                correct_score = c["score"]
                break

        p_at_1 = 1 if rank == 1 else 0
        p_at_3 = 1 if rank is not None else 0
        mrr    = (1 / rank) if rank is not None else 0.0

        results.append({
            "query":        query,
            "expected":     f"{exp_server}.{exp_tool}",
            "got":          f"{candidates[0]['server_id']}.{candidates[0]['tool_name']}" if candidates else "—",
            "rank":         rank,
            "p_at_1":       p_at_1,
            "p_at_3":       p_at_3,
            "mrr":          mrr,
            "score":        correct_score,
            "category":     category,
        })

        # Accumulate category stats
        if category not in category_stats:
            category_stats[category] = {"p1": [], "p3": [], "mrr": [], "scores": []}
        category_stats[category]["p1"].append(p_at_1)
        category_stats[category]["p3"].append(p_at_3)
        category_stats[category]["mrr"].append(mrr)
        if correct_score > 0:
            category_stats[category]["scores"].append(correct_score)

    # ── Print per-query results ───────────────────────────────────────────────
    print(f"{'Query':<45} {'Expected':<25} {'Got':<25} {'Rank':<6} {'Score':<8} {'P@1'}")
    print("-"*115)
    for r_item in results:
        rank_str  = str(r_item["rank"]) if r_item["rank"] else "✗"
        p1_str    = "✓" if r_item["p_at_1"] else "✗"
        score_str = f"{r_item['score']:.4f}" if r_item["score"] > 0 else "—"
        query_str = r_item["query"][:44]
        print(
            f"{query_str:<45} "
            f"{r_item['expected']:<25} "
            f"{r_item['got']:<25} "
            f"{rank_str:<6} "
            f"{score_str:<8} "
            f"{p1_str}"
        )

    # ── Overall metrics ───────────────────────────────────────────────────────
    total         = len(results)
    p_at_1_score  = sum(r["p_at_1"] for r in results) / total
    p_at_3_score  = sum(r["p_at_3"] for r in results) / total
    mrr_score     = sum(r["mrr"]    for r in results) / total
    avg_score     = sum(r["score"]  for r in results if r["score"] > 0) / max(sum(1 for r in results if r["score"] > 0), 1)

    print("\n" + "="*65)
    print("OVERALL METRICS")
    print("="*65)
    print(f"  Queries evaluated : {total}")
    print(f"  Precision@1       : {p_at_1_score:.1%}   (correct tool is #1 result)")
    print(f"  Precision@3       : {p_at_3_score:.1%}   (correct tool in top 3)")
    print(f"  MRR               : {mrr_score:.4f}  (Mean Reciprocal Rank)")
    print(f"  Avg Match Score   : {avg_score:.4f}  (similarity of correct matches)")

    # ── Per-category breakdown ────────────────────────────────────────────────
    print("\n" + "="*65)
    print("BY CATEGORY")
    print("="*65)
    print(f"  {'Category':<15} {'P@1':>6} {'P@3':>6} {'MRR':>8} {'Avg Score':>10}")
    print("  " + "-"*47)
    for cat, stats in category_stats.items():
        n       = len(stats["p1"])
        cat_p1  = sum(stats["p1"])  / n
        cat_p3  = sum(stats["p3"])  / n
        cat_mrr = sum(stats["mrr"]) / n
        cat_avg = sum(stats["scores"]) / max(len(stats["scores"]), 1)
        print(
            f"  {cat:<15} "
            f"{cat_p1:>5.1%} "
            f"{cat_p3:>5.1%} "
            f"{cat_mrr:>8.4f} "
            f"{cat_avg:>10.4f}"
        )

    # ── Assessment ───────────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("ASSESSMENT")
    print("="*65)
    if p_at_1_score >= 0.85:
        grade = "EXCELLENT ✓"
        note  = "Production-ready. Semantic routing reliable at scale."
    elif p_at_1_score >= 0.70:
        grade = "GOOD ✓"
        note  = "Suitable for production. Consider richer tool descriptions."
    elif p_at_1_score >= 0.55:
        grade = "ACCEPTABLE ~"
        note  = "Works but needs improvement. Enrich descriptions or tune threshold."
    else:
        grade = "NEEDS WORK ✗"
        note  = "Below threshold. Review tool descriptions and embedding model."

    print(f"  Grade  : {grade}")
    print(f"  Note   : {note}")
    print(f"  Threshold used : score >= 0.40 to accept semantic match")
    print("="*65 + "\n")

    return {
        "p_at_1":    p_at_1_score,
        "p_at_3":    p_at_3_score,
        "mrr":       mrr_score,
        "avg_score": avg_score,
    }


if __name__ == "__main__":
    run_benchmark()