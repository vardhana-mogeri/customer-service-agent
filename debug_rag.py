import database as db
import json

QUERY_TEXT = "how to do Parallel Query in PostgreSQL?"

knowledge_chunks = db.query_vector_db(QUERY_TEXT, k=5) # Let's ask for 5 results to see more

if not knowledge_chunks:
    print("\n[RESULT] The vector search returned ZERO results.")
    print("This is the root cause of the 'not in my knowledge base' response.")
    print("The query vector is not 'close' enough to any document vectors in the DB.")
else:
    print(f"\n[RESULT] The vector search returned {len(knowledge_chunks)} results:")
    for i, chunk in enumerate(knowledge_chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"Title: {chunk.get('title')}")
        print(f"URL: {chunk.get('url')}")
        # Print a snippet of the content to see what it's about
        content_snippet = chunk.get('content', '')[:300] + "..."
        print(f"Content Snippet: {content_snippet}")
        
print("\n--- Debugging Complete ---")