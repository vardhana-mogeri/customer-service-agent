# database.py

import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


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
