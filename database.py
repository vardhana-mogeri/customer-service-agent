# # database.py

# # Standard library imports
# import json
# import os
# import uuid
# from datetime import datetime
# from typing import List, Dict, Any, Optional

# # Third-party imports
# from dotenv import load_dotenv
# from psycopg2 import pool
# from psycopg2.extensions import connection
# from sentence_transformers import SentenceTransformer


# # Load environment variables from .env file
# load_dotenv()

# # --- CONFIGURATION ---
# DB_NAME = os.getenv("DB_NAME")
# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_HOST = os.getenv("DB_HOST")
# DB_PORT = os.getenv("DB_PORT")

# # This is the graph name for Apache AGE
# GRAPH_NAME = 'customer_support_graph'

# # Load the embedding model once to be used by the RAG function
# # This is efficient as it doesn't reload the model on every call.
# embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# # --- DATABASE CONNECTION POOLING ---
# # Initialize connection pool globally. It will be created on first successful connection attempt.
# conn_pool = None

# def initialize_connection_pool() -> None:
#     """
#     Initializes the global psycopg2 connection pool if it is not already set.

#     This function creates a `psycopg2.pool.SimpleConnectionPool` using global
#     database configuration variables (DB_NAME, DB_USER, etc.) and assigns it
#     to the global `conn_pool` variable.

#     Raises:
#         Exception: If the connection pool cannot be created (e.g., due to
#             invalid credentials or unreachable host). The original exception
#             is re-raised after logging the error.
#     """
#     global conn_pool
#     if conn_pool is None:
#         try:
#             # Only initialize if not already set
#             conn_pool = pool.SimpleConnectionPool(
#                 minconn=1,  # Minimum connections to keep open
#                 maxconn=10, # Maximum connections in the pool
#                 dbname=DB_NAME,
#                 user=DB_USER,
#                 password=DB_PASSWORD,
#                 host=DB_HOST,
#                 port=DB_PORT
#             )
#             print("Database connection pool initialized.")
#         except Exception as e:
#             print(f"Error initializing connection pool: {e}")
#             # Re-raise to indicate a critical setup failure
#             raise 

# def get_db_connection() -> Optional[connection]:
#     """
#     Retrieves and configures a database connection from the global pool.

#     This function performs several key tasks:
#     1.  Checks if the global connection pool (`conn_pool`) is initialized. If not,
#         it calls `initialize_connection_pool()`.
#     2.  Retrieves a single connection from the pool.
#     3.  Configures the connection for use with the Apache AGE extension by:
#         - Loading the 'age' extension.
#         - Setting the appropriate 'search_path'.
#         - Idempotently creating the specified graph if it does not already exist.

#     Returns:
#         Optional[connection]: A configured `psycopg2` connection object on
#         success, ready for database operations. Returns `None` if the connection
#         pool cannot be initialized or if a connection cannot be retrieved or
#         configured.
#     """
#     global conn_pool
#     if conn_pool is None:
#         try:
#             initialize_connection_pool()
#         except Exception:
#             # If pool initialization fails, return None
#             return None 

#     if conn_pool:
#         # Initialize conn to None before the try block
#         conn = None 
#         try:
#             conn = conn_pool.getconn()

#             # --- IMPORTANT: Setup AGE for every new session (connection) ---
#             with conn.cursor() as cursor:
#                 cursor.execute("LOAD 'age';")
#                 cursor.execute("SET search_path = ag_catalog, '$user', public;")

#                 # Check if the graph exists, if not create it (idempotent)
#                 cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname = %s;", (GRAPH_NAME,))
#                 if cursor.fetchone() is None:
#                     cursor.execute("SELECT create_graph(%s);", (GRAPH_NAME,))
#                     # Commit graph creation
#                     conn.commit() 
#                     print(f"Graph '{GRAPH_NAME}' created.")

#             return conn
#         except Exception as e:
#             print(f"Error getting connection from pool or setting up AGE: {e}")
#             # If an error occurs, ensure the connection is returned to the pool
#             if conn:
#                 # Return bad connection to pool for cleanup
#                 conn_pool.putconn(conn) 
#             return None
#     return None

# def create_or_update_ticket(ticket_id: str, user_id: int, description: str, log: str) -> bool:
#     """Idempotently creates a new ticket in the database.

#     This function checks if a ticket with the given `ticket_id` already exists
#     in the 'tickets' table. If it does not exist, a new ticket record is
#     inserted with the provided details. If the ticket already exists, the
#     function takes no action and returns successfully.

#     This design ensures that the operation can be safely repeated without
#     creating duplicate entries. Note: Despite the name, this function only
#     handles creation, not updates.

#     Args:
#         ticket_id (str): The unique identifier for the ticket.
#         user_id (int): The ID of the user associated with the ticket.
#         description (str): A detailed description of the ticket's issue or content.
#         log (str): A log entry or initial comment for the ticket.

#     Returns:
#         bool: True if the ticket was successfully created or if it already
#               existed. False if a database connection could not be established
#               or if an error occurred during the transaction.
#     """
#     conn = get_db_connection()
#     if not conn:
#         return False

#     try:
#         with conn.cursor() as cursor:
#             # Check for existence to ensure idempotency
#             cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = %s;", (ticket_id,))
#             if cursor.fetchone():
#                 print(f"Ticket {ticket_id} already exists. Skipping creation.")
#                 return True

#             # Insert the new ticket record
#             cursor.execute(
#                 "INSERT INTO tickets (ticket_id, user_id, description, log) VALUES (%s, %s, %s, %s);",
#                 (ticket_id, user_id, description, log)
#             )
#             conn.commit()
#             print(f"Successfully created ticket {ticket_id}.")
#         return True
#     except Exception as e:
#         print(f"An error occurred in create_or_update_ticket: {e}")
#         conn.rollback()
#         return False
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)


# # --- RAG: KNOWLEDGE BASE FUNCTIONS (pgvector) ---

# def query_vector_db(query_text: str, k: int = 3) -> list[dict]:
#     """Finds the most relevant documents for a given text query.

#     This function converts the input `query_text` into a numerical vector
#     embedding using a pre-loaded sentence-transformer model. It then queries a
#     PostgreSQL database, presumably equipped with the pgvector extension,
#     to find the `k` most semantically similar documents.

#     The similarity search is performed using the L2 distance operator (`<=>`)
#     on the stored embeddings in the `pg_docs` table.

#     Args:
#         query_text (str): The natural language query to search for.
#         k (int, optional): The maximum number of relevant documents to return.
#             Defaults to 3.

#     Returns:
#         list[dict]: A list of the top `k` matching documents, sorted by
#             relevance. Each dictionary contains 'content', 'title', and 'url'.
#             Returns an empty list if a database connection fails or an
#             error occurs during the query.
#     """
#     query_embedding = embedding_model.encode(query_text).tolist()
    
#     conn = get_db_connection()
#     if not conn:
#         return []
        
#     results = []
#     try:
#         with conn.cursor() as cursor:
#             # The '<=>' operator calculates the L2 distance, which is inversely
#             # related to cosine similarity for normalized vectors.
#             # We order by this distance to get the "closest" matches first.
#             cursor.execute(
#                 """
#                 SELECT content, title, url
#                 FROM pg_docs
#                 ORDER BY embedding <=> %s
#                 LIMIT %s;
#                 """,
#                 (str(query_embedding), k)
#             )
#             rows = cursor.fetchall()
#             for row in rows:
#                 results.append({"content": row[0], "title": row[1], "url": row[2]})
#     except Exception as e:
#         print(f"An error occurred during vector query: {e}")
#         # On error, results will be an empty list, which is the correct
#         # response for a failed query.
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)
            
#     return results

# # --- SoR: SYSTEM OF RECORD FUNCTIONS (Tickets) ---

# def create_ticket(user_id: int, description: str) -> Optional[str]:
#     """Creates a new support ticket and stores it in the database.

#     This function generates a unique, human-readable ticket ID (e.g.,
#     'TICKET-A1B2C3D4') and creates an initial log entry with the current UTC
#     timestamp. It then inserts a new record into the 'tickets' table
#     with the provided user ID and description.

#     The entire operation is performed within a single database transaction,
#     which is committed on success or rolled back on failure to ensure data
#     integrity.

#     Args:
#         user_id (int): The identifier for the user creating the ticket.
#         description (str): The problem description or content for the ticket.

#     Returns:
#         Optional[str]: The unique string ID of the newly created ticket upon
#         successful insertion. Returns `None` if a database connection
#         fails or if any error occurs during the transaction.
#     """
#     ticket_id = f"TICKET-{str(uuid.uuid4())[:8].upper()}"
#     log_entry = f"{datetime.utcnow().isoformat()}: Ticket created."
    
#     conn = get_db_connection()
#     if not conn:
#         return None
        
#     try:
#         with conn.cursor() as cursor:
#             cursor.execute(
#                 "INSERT INTO tickets (ticket_id, user_id, description, log) VALUES (%s, %s, %s, %s);",
#                 (ticket_id, user_id, description, log_entry)
#             )
#         conn.commit()
#         return ticket_id
#     except Exception as e:
#         print(f"An error occurred creating ticket: {e}")
#         conn.rollback()
#         return None
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)

# def get_tickets_by_user(user_id: int) -> Optional[List[Dict[str, Any]]]:
#     """Retrieves all tickets for a specific user, sorted by creation date.

#     This function queries the `tickets` table for all records matching the
#     provided `user_id`. The results are ordered in descending order of their
#     creation time (`created_at` column), ensuring that the newest tickets
#     appear first in the returned list.

#     Args:
#         user_id (int): The unique identifier of the user whose tickets are
#             to be fetched.

#     Returns:
#         Optional[List[Dict[str, Any]]]: A list of dictionaries, where each
#         dictionary represents a single ticket and contains the 'ticket_id',
#         'status', and 'description'. If the user has no tickets, an empty
#         list is returned. Returns `None` if a database connection cannot
#         be established or if an error occurs during the query.
#     """
#     conn = get_db_connection()
#     if not conn:
#         return None

#     tickets: List[Dict[str, Any]] = []
#     try:
#         with conn.cursor() as cursor:
#             # Query for tickets and order by the newest first
#             cursor.execute(
#                 "SELECT ticket_id, status, description FROM tickets WHERE user_id = %s ORDER BY created_at DESC;",
#                 (user_id,)
#             )
#             rows = cursor.fetchall()
#             for row in rows:
#                 tickets.append({"ticket_id": row[0], "status": row[1], "description": row[2]})
#         return tickets
#     except Exception as e:
#         print(f"An error occurred getting tickets by user: {e}")
#         return None
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)


# # --- CAG: GRAPH MEMORY FUNCTIONS (Apache AGE) ---

# def add_message_to_graph(user_id: int, session_id: str, message_text: str, author: str) -> bool:
#     """Adds a message node to a conversation graph in Apache AGE.

#     This function models a conversation by creating and linking nodes in the
#     graph. It follows this structure: (User)-[:HAS_SESSION]->(Session)-[:CONTAINS]->(Message).
#     It uses `MERGE` to idempotently create the User and Session nodes, ensuring
#     they are not duplicated. A new `Message` node is then created for each call.

#     **Query Construction Method:**
#     This function manually constructs the Cypher query string. This is a deliberate
#     choice to work around the specific parsing requirements of the Apache AGE
#     `cypher()` function, which expects the entire query as a single string literal.

#     To prevent SQL or Cypher injection vulnerabilities, all external inputs
#     (`message_text`, `author`) are safely escaped into valid JSON string
#     literals using `json.dumps()` before being interpolated into the query.
#     The final command is then wrapped in PostgreSQL's dollar-quoting (`$$...$$`).

#     Args:
#         user_id (int): The identifier for the user who owns the session.
#         session_id (str): The unique identifier for the conversation session.
#         message_text (str): The content of the message to be added.
#         author (str): The author of the message (e.g., 'user', 'assistant').

#     Returns:
#         bool: True if the message was successfully added and the transaction
#               was committed. False if a database connection or query execution
#               error occurred.
#     """
#     conn = get_db_connection()
#     if not conn:
#         return False

#     try:
#         # 1. Safely escape user-provided strings into valid JSON string literals.
#         safe_message_text = json.dumps(message_text)
#         safe_author = json.dumps(author)

#         # 2. Construct the inner Cypher query using the escaped values.
#         cypher_query = f"""
#         MERGE (u:User {{id: {user_id}}})
#         MERGE (s:Session {{id: '{session_id}'}})
#         MERGE (u)-[:HAS_SESSION]->(s)
        
#         CREATE (m:Message {{
#             text: {safe_message_text},
#             author: {safe_author},
#             timestamp: timestamp()
#         }})
#         CREATE (s)-[:CONTAINS]->(m)
#         """

#         # 3. Construct the final outer SQL command, wrapping the Cypher query
#         # in the required dollar-quoted ($$) syntax for AGE.
#         final_sql_command = f"""
#             SELECT * FROM cypher('{GRAPH_NAME}', $$
#                 {cypher_query}
#             $$) AS (v agtype);
#         """

#         # 4. Execute the complete command. No parameters are needed here because
#         # the entire string has been built safely.
#         with conn.cursor() as cursor:
#             cursor.execute(final_sql_command)
        
#         conn.commit()
#         return True
#     except Exception as e:
#         print(f"An error occurred adding message to graph: {e}")
#         conn.rollback()
#         return False
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)


# def get_conversation_history(session_id: str, n: int = 5) -> List[Dict[str, Any]]:
#     """Retrieves the last N messages from a conversation session graph.

#     This function queries the Apache AGE graph to find a `Session` node matching
#     the given `session_id`. It then traverses the graph to find all connected
#     `Message` nodes.

#     The Cypher query fetches the messages and sorts them by their timestamp in
#     descending order (newest first) to efficiently retrieve only the most
# e   recent `n` messages. The final list is then reversed in Python to present
#     the conversation in the correct chronological order (oldest to newest).

#     The function also handles the conversion of data from AGE's native `agtype`
#     format into standard Python strings.

#     Args:
#         session_id (str): The unique identifier for the conversation session.
#         n (int, optional): The number of recent messages to retrieve.
#             Defaults to 5.

#     Returns:
#         List[Dict[str, Any]]: A list of dictionaries, where each dictionary
#         represents a message and contains 'author' and 'text'. The list is
#         sorted in chronological order. Returns an empty list if the session
#         is not found or if a database error occurs.
#     """
#     conn = get_db_connection()
#     if not conn:
#         return []

#     # Note: session_id is directly embedded. This assumes session_id is a
#     # controlled value (like a UUID) and not arbitrary user input.
#     cypher_query = f"""
#     SELECT * FROM cypher('{GRAPH_NAME}', $$
#         MATCH (s:Session {{id: '{session_id}'}})-[:CONTAINS]->(m:Message)
#         RETURN m.author, m.text, m.timestamp
#         ORDER BY m.timestamp DESC
#         LIMIT {n}
#     $$) AS (author agtype, text agtype, ts agtype);
#     """
    
#     history: List[Dict[str, Any]] = []
#     try:
#         with conn.cursor() as cursor:
#             cursor.execute(cypher_query)
#             rows = cursor.fetchall()
#             for row in rows:
#                 # AGE returns agtype objects; convert them to native Python types resulting json like literal.
#                 author_str = str(row[0]).strip('"') if row[0] else None
#                 text_str = str(row[1]).strip('"') if row[1] else None
#                 history.append({"author": author_str, "text": text_str})
        
#         # The query returns results in reverse chronological order (newest first), so reversing.
#         return history[::-1]
#     except Exception as e:
#         print(f"An error occurred getting conversation history: {e}")
#         return []
#     finally:
#         # Always return the connection to the pool
#         if conn and conn_pool:
#             conn_pool.putconn(conn)


# # --- Example Usage for Testing ---
# if __name__ == '__main__':
#     print("Testing database functions...")
    
#     # Initialize the pool for testing
#     try:
#         initialize_connection_pool()
#     except Exception as e:
#         print(f"Failed to initialize pool for testing: {e}. Exiting tests.")
#         exit()

#     # Test RAG
#     print("\n--- Testing RAG ---")
#     search_results = query_vector_db("how to do parallel query?")
#     if search_results:
#         print(f"Found {len(search_results)} relevant documents.")
#         print("Top result:", search_results[0]['title'])
#     else:
#         print("RAG test failed or returned no results. Make sure pg_docs table is populated.")

#     # Test SoR
#     print("\n--- Testing SoR ---")
#     new_ticket_id = create_ticket(user_id=1, description="My database is slow.")
#     if new_ticket_id:
#         print(f"Created ticket: {new_ticket_id}")
#         ticket_details = get_ticket_details(new_ticket_id)
#         print("Retrieved ticket details:", ticket_details)
#     else:
#         print("SoR test failed.")

#     # Test CAG
#     print("\n--- Testing CAG ---")
#     test_session = "test_session_123"
#     add_message_to_graph(user_id=1, session_id=test_session, message_text="Hello, agent!", author="user")
#     add_message_to_graph(user_id=1, session_id=test_session, message_text="Hello! How can I help?", author="agent")
#     history = get_conversation_history(test_session)
#     if history:
#         print(f"Retrieved conversation history with {len(history)} messages.")
#         for msg in history:
#             print(f"- {msg['author']}: {msg['text']}")
#     else:
#         print("CAG test failed. Check AGE setup and graph creation.")

#     # IMPORTANT: Close the connection pool when your application shuts down
#     # In a web app, this might be handled by a shutdown hook.
#     # For this script, we explicitly close it here.
#     if conn_pool:
#         conn_pool.closeall()
#         print("\nDatabase connection pool closed.")

# database.py

# Standard library imports
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Third-party imports
from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extensions import connection
from sentence_transformers import SentenceTransformer


# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# This is the graph name for Apache AGE
GRAPH_NAME = 'customer_support_graph'

# Load the embedding model once to be used by the RAG function
# This is efficient as it doesn't reload the model on every call.
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# --- DATABASE CONNECTION POOLING ---
# Initialize connection pool globally. It will be created on first successful connection attempt.
conn_pool = None

def initialize_connection_pool() -> None:
    """
    Initializes the global psycopg2 connection pool if it is not already set.

    This function creates a `psycopg2.pool.SimpleConnectionPool` using global
    database configuration variables (DB_NAME, DB_USER, etc.) and assigns it
    to the global `conn_pool` variable.

    Raises:
        Exception: If the connection pool cannot be created (e.g., due to
            invalid credentials or unreachable host). The original exception
            is re-raised after logging the error.
    """
    global conn_pool
    if conn_pool is None:
        try:
            # Only initialize if not already set
            conn_pool = pool.SimpleConnectionPool(
                minconn=1,  # Minimum connections to keep open
                maxconn=10, # Maximum connections in the pool
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            print("Database connection pool initialized.")
        except Exception as e:
            print(f"Error initializing connection pool: {e}")
            # Re-raise to indicate a critical setup failure
            raise 

def get_db_connection() -> Optional[connection]:
    """
    Retrieves and configures a database connection from the global pool.

    This function performs several key tasks:
    1.  Checks if the global connection pool (`conn_pool`) is initialized. If not,
        it calls `initialize_connection_pool()`.
    2.  Retrieves a single connection from the pool.
    3.  Configures the connection for use with the Apache AGE extension by:
        - Loading the 'age' extension.
        - Setting the appropriate 'search_path'.
        - Idempotently creating the specified graph if it does not already exist.

    Returns:
        Optional[connection]: A configured `psycopg2` connection object on
        success, ready for database operations. Returns `None` if the connection
        pool cannot be initialized or if a connection cannot be retrieved or
        configured.
    """
    global conn_pool
    if conn_pool is None:
        try:
            initialize_connection_pool()
        except Exception:
            # If pool initialization fails, return None
            return None 

    if conn_pool:
        # Initialize conn to None before the try block
        conn = None 
        try:
            conn = conn_pool.getconn()

            # --- IMPORTANT: Setup AGE for every new session (connection) ---
            with conn.cursor() as cursor:
                cursor.execute("LOAD 'age';")
                cursor.execute("SET search_path = ag_catalog, '$user', public;")

                # Check if the graph exists, if not create it (idempotent)
                cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname = %s;", (GRAPH_NAME,))
                if cursor.fetchone() is None:
                    cursor.execute("SELECT create_graph(%s);", (GRAPH_NAME,))
                    # Commit graph creation
                    conn.commit() 
                    print(f"Graph '{GRAPH_NAME}' created.")

            return conn
        except Exception as e:
            print(f"Error getting connection from pool or setting up AGE: {e}")
            # If an error occurs, ensure the connection is returned to the pool
            if conn:
                # Return bad connection to pool for cleanup
                conn_pool.putconn(conn) 
            return None
    return None

def create_or_update_ticket(ticket_id: str, user_id: int, description: str, log: str) -> bool:
    """Idempotently creates a new ticket in the database.

    This function checks if a ticket with the given `ticket_id` already exists
    in the 'tickets' table. If it does not exist, a new ticket record is
    inserted with the provided details. If the ticket already exists, the
    function takes no action and returns successfully.

    This design ensures that the operation can be safely repeated without
    creating duplicate entries. Note: Despite the name, this function only
    handles creation, not updates.

    Args:
        ticket_id (str): The unique identifier for the ticket.
        user_id (int): The ID of the user associated with the ticket.
        description (str): A detailed description of the ticket's issue or content.
        log (str): A log entry or initial comment for the ticket.

    Returns:
        bool: True if the ticket was successfully created or if it already
              existed. False if a database connection could not be established
              or if an error occurred during the transaction.
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cursor:
            # Check for existence to ensure idempotency
            cursor.execute("SELECT ticket_id FROM tickets WHERE ticket_id = %s;", (ticket_id,))
            if cursor.fetchone():
                print(f"Ticket {ticket_id} already exists. Skipping creation.")
                return True

            # Insert the new ticket record
            cursor.execute(
                "INSERT INTO tickets (ticket_id, user_id, description, log) VALUES (%s, %s, %s, %s);",
                (ticket_id, user_id, description, log)
            )
            conn.commit()
            print(f"Successfully created ticket {ticket_id}.")
        return True
    except Exception as e:
        print(f"An error occurred in create_or_update_ticket: {e}")
        conn.rollback()
        return False
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


# --- RAG: KNOWLEDGE BASE FUNCTIONS (pgvector) ---

def query_vector_db(query_text: str, k: int = 3) -> list[dict]:
    """Finds the most relevant documents for a given text query.

    This function converts the input `query_text` into a numerical vector
    embedding using a pre-loaded sentence-transformer model. It then queries a
    PostgreSQL database, presumably equipped with the pgvector extension,
    to find the `k` most semantically similar documents.

    The similarity search is performed using the L2 distance operator (`<=>`)
    on the stored embeddings in the `pg_docs` table.

    Args:
        query_text (str): The natural language query to search for.
        k (int, optional): The maximum number of relevant documents to return.
            Defaults to 3.

    Returns:
        list[dict]: A list of the top `k` matching documents, sorted by
            relevance. Each dictionary contains 'content', 'title', and 'url'.
            Returns an empty list if a database connection fails or an
            error occurs during the query.
    """
    query_embedding = embedding_model.encode(query_text).tolist()
    
    conn = get_db_connection()
    if not conn:
        return []
        
    results = []
    try:
        with conn.cursor() as cursor:
            # The '<=>' operator calculates the L2 distance, which is inversely
            # related to cosine similarity for normalized vectors.
            # We order by this distance to get the "closest" matches first.
            cursor.execute(
                """
                SELECT content, title, url
                FROM pg_docs
                ORDER BY embedding <=> %s
                LIMIT %s;
                """,
                (str(query_embedding), k)
            )
            rows = cursor.fetchall()
            for row in rows:
                results.append({"content": row[0], "title": row[1], "url": row[2]})
    except Exception as e:
        print(f"An error occurred during vector query: {e}")
        # On error, results will be an empty list, which is the correct
        # response for a failed query.
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)
            
    return results

# --- SoR: SYSTEM OF RECORD FUNCTIONS (Tickets) ---

def create_ticket(user_id: int, description: str) -> Optional[str]:
    """Creates a new support ticket and stores it in the database.

    This function generates a unique, human-readable ticket ID (e.g.,
    'TICKET-A1B2C3D4') and creates an initial log entry with the current UTC
    timestamp. It then inserts a new record into the 'tickets' table
    with the provided user ID and description.

    The entire operation is performed within a single database transaction,
    which is committed on success or rolled back on failure to ensure data
    integrity.

    Args:
        user_id (int): The identifier for the user creating the ticket.
        description (str): The problem description or content for the ticket.

    Returns:
        Optional[str]: The unique string ID of the newly created ticket upon
        successful insertion. Returns `None` if a database connection
        fails or if any error occurs during the transaction.
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
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


def get_ticket_details(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves all details for a given ticket ID from the database.

    This function queries the `tickets` table for a single record matching the
    provided `ticket_id`. If a matching record is found, it is formatted into a
    dictionary containing the ticket's essential fields.

    Args:
        ticket_id (str): The unique identifier of the ticket to retrieve.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the ticket's
        'ticket_id', 'user_id', 'status', 'description', and 'log' if the
        ticket is found. Returns `None` if the ticket does not exist, if a
        database connection fails, or if an error occurs during the query.
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT ticket_id, user_id, status, description, log FROM tickets WHERE ticket_id = %s;",
                (ticket_id,)
            )
            ticket = cursor.fetchone()
            if ticket:
                return {
                    "ticket_id": ticket[0],
                    "user_id": ticket[1],
                    "status": ticket[2],
                    "description": ticket[3],
                    "log": ticket[4]
                }
            # Return None if no ticket was found
            return None
    except Exception as e:
        print(f"An error occurred getting ticket details: {e}")
        return None
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


def get_tickets_by_user(user_id: int) -> Optional[List[Dict[str, Any]]]:
    """Retrieves all tickets for a specific user, sorted by creation date.

    This function queries the `tickets` table for all records matching the
    provided `user_id`. The results are ordered in descending order of their
    creation time (`created_at` column), ensuring that the newest tickets
    appear first in the returned list.

    Args:
        user_id (int): The unique identifier of the user whose tickets are
            to be fetched.

    Returns:
        Optional[List[Dict[str, Any]]]: A list of dictionaries, where each
        dictionary represents a single ticket and contains the 'ticket_id',
        'status', and 'description'. If the user has no tickets, an empty
        list is returned. Returns `None` if a database connection cannot
        be established or if an error occurs during the query.
    """
    conn = get_db_connection()
    if not conn:
        return None

    tickets: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cursor:
            # Query for tickets and order by the newest first
            cursor.execute(
                "SELECT ticket_id, status, description FROM tickets WHERE user_id = %s ORDER BY created_at DESC;",
                (user_id,)
            )
            rows = cursor.fetchall()
            for row in rows:
                tickets.append({"ticket_id": row[0], "status": row[1], "description": row[2]})
        return tickets
    except Exception as e:
        print(f"An error occurred getting tickets by user: {e}")
        return None
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


# --- CAG: GRAPH MEMORY FUNCTIONS (Apache AGE) ---

def add_message_to_graph(user_id: int, session_id: str, message_text: str, author: str) -> bool:
    """Adds a message node to a conversation graph in Apache AGE.

    This function models a conversation by creating and linking nodes in the
    graph. It follows this structure: (User)-[:HAS_SESSION]->(Session)-[:CONTAINS]->(Message).
    It uses `MERGE` to idempotently create the User and Session nodes, ensuring
    they are not duplicated. A new `Message` node is then created for each call.

    **Query Construction Method:**
    This function manually constructs the Cypher query string. This is a deliberate
    choice to work around the specific parsing requirements of the Apache AGE
    `cypher()` function, which expects the entire query as a single string literal.

    To prevent SQL or Cypher injection vulnerabilities, all external inputs
    (`message_text`, `author`) are safely escaped into valid JSON string
    literals using `json.dumps()` before being interpolated into the query.
    The final command is then wrapped in PostgreSQL's dollar-quoting (`$$...$$`).

    Args:
        user_id (int): The identifier for the user who owns the session.
        session_id (str): The unique identifier for the conversation session.
        message_text (str): The content of the message to be added.
        author (str): The author of the message (e.g., 'user', 'assistant').

    Returns:
        bool: True if the message was successfully added and the transaction
              was committed. False if a database connection or query execution
              error occurred.
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        # 1. Safely escape user-provided strings into valid JSON string literals.
        safe_message_text = json.dumps(message_text)
        safe_author = json.dumps(author)

        # 2. Construct the inner Cypher query using the escaped values.
        cypher_query = f"""
        MERGE (u:User {{id: {user_id}}})
        MERGE (s:Session {{id: '{session_id}'}})
        MERGE (u)-[:HAS_SESSION]->(s)
        
        CREATE (m:Message {{
            text: {safe_message_text},
            author: {safe_author},
            timestamp: timestamp()
        }})
        CREATE (s)-[:CONTAINS]->(m)
        """

        # 3. Construct the final outer SQL command, wrapping the Cypher query
        # in the required dollar-quoted ($$) syntax for AGE.
        final_sql_command = f"""
            SELECT * FROM cypher('{GRAPH_NAME}', $$
                {cypher_query}
            $$) AS (v agtype);
        """

        # 4. Execute the complete command. No parameters are needed here because
        # the entire string has been built safely.
        with conn.cursor() as cursor:
            cursor.execute(final_sql_command)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"An error occurred adding message to graph: {e}")
        conn.rollback()
        return False
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


def get_conversation_history(session_id: str, n: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the last N messages from a conversation session graph.

    This function queries the Apache AGE graph to find a `Session` node matching
    the given `session_id`. It then traverses the graph to find all connected
    `Message` nodes.

    The Cypher query fetches the messages and sorts them by their timestamp in
    descending order (newest first) to efficiently retrieve only the most
    recent `n` messages. The final list is then reversed in Python to present
    the conversation in the correct chronological order (oldest to newest).

    The function also handles the conversion of data from AGE's native `agtype`
    format into standard Python strings.

    Args:
        session_id (str): The unique identifier for the conversation session.
        n (int, optional): The number of recent messages to retrieve.
            Defaults to 5.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary
        represents a message and contains 'author' and 'text'. The list is
        sorted in chronological order. Returns an empty list if the session
        is not found or if a database error occurs.
    """
    conn = get_db_connection()
    if not conn:
        return []

    # Note: session_id is directly embedded. This assumes session_id is a
    # controlled value (like a UUID) and not arbitrary user input.
    cypher_query = f"""
    SELECT * FROM cypher('{GRAPH_NAME}', $$
        MATCH (s:Session {{id: '{session_id}'}})-[:CONTAINS]->(m:Message)
        RETURN m.author, m.text, m.timestamp
        ORDER BY m.timestamp DESC
        LIMIT {n}
    $$) AS (author agtype, text agtype, ts agtype);
    """
    
    history: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cursor:
            cursor.execute(cypher_query)
            rows = cursor.fetchall()
            for row in rows:
                # AGE returns agtype objects; convert them to native Python types resulting json like literal.
                author_str = str(row[0]).strip('"') if row[0] else None
                text_str = str(row[1]).strip('"') if row[1] else None
                history.append({"author": author_str, "text": text_str})
        
        # The query returns results in reverse chronological order (newest first), so reversing.
        return history[::-1]
    except Exception as e:
        print(f"An error occurred getting conversation history: {e}")
        return []
    finally:
        # Always return the connection to the pool
        if conn and conn_pool:
            conn_pool.putconn(conn)


# --- Example Usage for Testing ---
if __name__ == '__main__':
    print("Testing database functions...")
    
    # Initialize the pool for testing
    try:
        initialize_connection_pool()
    except Exception as e:
        print(f"Failed to initialize pool for testing: {e}. Exiting tests.")
        exit()

    # Test RAG
    print("\n--- Testing RAG ---")
    search_results = query_vector_db("how to do parallel query?")
    if search_results:
        print(f"Found {len(search_results)} relevant documents.")
        print("Top result:", search_results[0]['title'])
    else:
        print("RAG test failed or returned no results. Make sure pg_docs table is populated.")

    # Test SoR
    print("\n--- Testing SoR ---")
    new_ticket_id = create_ticket(user_id=1, description="My database is slow.")
    if new_ticket_id:
        print(f"Created ticket: {new_ticket_id}")
        # RESTORED: Test call for the get_ticket_details function
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
        print("CAG test failed. Check AGE setup and graph creation.")

    # IMPORTANT: Close the connection pool when your application shuts down
    # In a web app, this might be handled by a shutdown hook.
    # For this script, we explicitly close it here.
    if conn_pool:
        conn_pool.closeall()
        print("\nDatabase connection pool closed.")