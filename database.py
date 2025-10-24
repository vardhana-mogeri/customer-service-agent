# database.py

import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import uuid
from datetime import datetime
from sentence_transformers import SentenceTransformer


# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# This is the graph name we will use for Apache AGE
GRAPH_NAME = 'customer_support_graph'

# Load the embedding model once to be used by the RAG function
# This is efficient as it doesn't reload the model on every call.
embedding_model = SentenceTransformer('all-MiniLM-L6v2')


# --- DATABASE CONNECTION ---

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database and sets up AGE.
    Returns the connection object.
    """
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        print("Database connection established.")
        
        # --- IMPORTANT: Setup AGE for every new session ---
        with conn.cursor() as cursor:
            cursor.execute("LOAD 'age';")
            cursor.execute("SET search_path = ag_catalog, '$user', public;")
            
            # Check if the graph exists, if not create it
            cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname = %s;", (GRAPH_NAME,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("SELECT create_graph({});").format(sql.Identifier(GRAPH_NAME)))
                print(f"Graph '{GRAPH_NAME}' created.")

        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        return None

# --- RAG: KNOWLEDGE BASE FUNCTIONS (pgvector) ---

def query_vector_db(query_text: str, k: int = 3) -> list[dict]:
    """
    Queries the knowledge base for the most relevant chunks of text.

    Args:
        query_text: The user's query.
        k: The number of results to return.

    Returns:
        A list of dictionaries, each containing the content, title, and url.
    """
    query_embedding = embedding_model.encode(query_text).tolist()
    
    conn = get_db_connection()
    if not conn:
        return []
        
    results = []
    try:
        with conn.cursor() as cursor:
            # Note: The table name is pg_docs as per your setup
            # The operator '<=>' calculates the L2 distance
            cursor.execute(
                "SELECT content, title, url FROM pg_docs ORDER BY embedding <=> %s LIMIT %s;",
                (str(query_embedding), k)
            )
            rows = cursor.fetchall()
            for row in rows:
                results.append({"content": row[0], "title": row[1], "url": row[2]})
    except Exception as e:
        print(f"An error occurred during vector query: {e}")
    finally:
        if conn:
            conn.close()
            
    return results

# --- SoR: SYSTEM OF RECORD FUNCTIONS (Tickets) ---

def create_ticket(user_id: int, description: str) -> str | None:
    """
    Creates a new support ticket in the database.

    Returns:
        The ID of the newly created ticket, or None on failure.
    """
    ticket_id = f"TICKET-{str(uuid.uuid4())[:8].upper()}"
    log_entry = f"{datetime.utcnow().isoformat()}: Ticket created."
    
    conn = get_db_connection()
    if not conn:
        return None
        
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tickets (ticket_id, user_id, description, log) VALUES (%s, %s, %s, %s);",
                (ticket_id, user_id, description, log_entry)
            )
        conn.commit()
        return ticket_id
    except Exception as e:
        print(f"An error occurred creating ticket: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def get_ticket_details(ticket_id: str) -> dict | None:
    """Retrieves all details for a given ticket ID."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ticket_id, user_id, status, description, log FROM tickets WHERE ticket_id = %s;", (ticket_id,))
            ticket = cursor.fetchone()
            if ticket:
                return {
                    "ticket_id": ticket[0], "user_id": ticket[1], "status": ticket[2],
                    "description": ticket[3], "log": ticket[4]
                }
            return None
    except Exception as e:
        print(f"An error occurred getting ticket details: {e}")
        return None
    finally:
        if conn:
            conn.close()

# --- CAG: GRAPH MEMORY FUNCTIONS (Apache AGE) ---

def add_message_to_graph(user_id: int, session_id: str, message_text: str, author: str):
    """
    Adds a new message to the conversation graph for a user and session.
    Uses MERGE to be idempotent (avoid creating duplicate users/sessions).
    """
    conn = get_db_connection()
    if not conn:
        return

    cypher_query = f"""
    SELECT * FROM cypher('{GRAPH_NAME}', $$
        MERGE (u:User {{id: {user_id}}})
        MERGE (s:Session {{id: '{session_id}'}})
        MERGE (u)-[:HAS_SESSION]->(s)
        
        CREATE (m:Message {{
            text: '{message_text.replace("'", "''")}', -- Basic sanitation for single quotes
            author: '{author}',
            timestamp: timestamp()
        }})
        CREATE (s)-[:CONTAINS]->(m)
    $$) AS (v agtype);
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(cypher_query)
        conn.commit()
    except Exception as e:
        print(f"An error occurred adding message to graph: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_conversation_history(session_id: str, n: int = 5) -> list[dict]:
    """
    Retrieves the last n messages from the conversation history for a session.
    """
    conn = get_db_connection()
    if not conn:
        return []

    cypher_query = f"""
    SELECT * FROM cypher('{GRAPH_NAME}', $$
        MATCH (s:Session {{id: '{session_id}'}})-[:CONTAINS]->(m:Message)
        RETURN m.author, m.text, m.timestamp
        ORDER BY m.timestamp DESC
        LIMIT {n}
    $$) AS (author agtype, text agtype, ts agtype);
    """
    
    history = []
    try:
        with conn.cursor() as cursor:
            cursor.execute(cypher_query)
            rows = cursor.fetchall()
            for row in rows:
                history.append({"author": row[0], "text": row[1]})
        # The results are in reverse chronological order, so we reverse them back
        return history[::-1]
    except Exception as e:
        print(f"An error occurred getting conversation history: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- Example Usage for Testing ---
if __name__ == '__main__':
    print("Testing database functions...")
    
    # Test RAG
    print("\n--- Testing RAG ---")
    search_results = query_vector_db("how to do parallel query?")
    if search_results:
        print(f"Found {len(search_results)} relevant documents.")
        print("Top result:", search_results[0]['title'])
    else:
        print("RAG test failed or returned no results.")

    # Test SoR
    print("\n--- Testing SoR ---")
    new_ticket_id = create_ticket(user_id=1, description="My database is slow.")
    if new_ticket_id:
        print(f"Created ticket: {new_ticket_id}")
        ticket_details = get_ticket_details(new_ticket_id)
        print("Retrieved ticket details:", ticket_details)
    else:
        print("SoR test failed.")

    # Test CAG
    print("\n--- Testing CAG ---")
    test_session = "test_session_123"
    add_message_to_graph(user_id=1, session_id=test_session, message_text="Hello, agent!", author="user")
    add_message_to_graph(user_id=1, session_id=test_session, message_text="Hello! How can I help?", author="agent")
    history = get_conversation_history(test_session)
    if history:
        print(f"Retrieved conversation history with {len(history)} messages.")
        for msg in history:
            print(f"- {msg['author']}: {msg['text']}")
    else:
        print("CAG test failed.")
