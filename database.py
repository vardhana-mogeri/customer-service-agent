# database.py

import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
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
