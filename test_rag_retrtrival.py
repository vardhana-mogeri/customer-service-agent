# test_rag_retrieval.py

"""
A standalone script to test the RAG retrieval functionality.

This script allows for a direct, isolated test of the vector database search
to debug and validate the quality of the knowledge base retrieval for a given query.

Usage:
    python3 test_rag_retrieval.py
"""

import database as db

# --- CONFIGURATION ---
# Change this query to test different retrieval scenarios.
TEST_QUERY = "how to do Parallel Query in PostgreSQL?"

def run_test():
    """Executes the RAG retrieval test and prints the results."""
    print("---" * 10)
    print(f"Executing RAG retrieval test...")
    print(f"Query: '{TEST_QUERY}'")
    print("---" * 10)
    
    # Call the database function directly, asking for 5 results for a thorough check.
    knowledge_chunks = db.query_vector_db(TEST_QUERY, k=5)
    
    if not knowledge_chunks:
        print("\n[RESULT] The vector search returned ZERO results.")
        print("This indicates a potential issue with the query, the embeddings, or the data in the pg_docs table.")
    else:
        print(f"\n[RESULT] The vector search returned {len(knowledge_chunks)} results:")
        for i, chunk in enumerate(knowledge_chunks):
            print(f"\n--- Chunk {i+1} ---")
            print(f"  Title: {chunk.get('title')}")
            print(f"  URL:   {chunk.get('url')}")
            content_snippet = chunk.get('content', '')[:250].replace('\n', ' ') + "..."
            print(f"  Content Snippet: {content_snippet}")
            
    print("\n" + "---" * 10)
    print("Test complete.")

if __name__ == "__main__":
    run_test()