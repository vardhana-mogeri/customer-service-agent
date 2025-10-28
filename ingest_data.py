import os
import psycopg2
import csv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

# --- FILE PATHS ---
# Path to your knowledge base CSV file
KB_CSV_PATH = 'mock_data/knowledge_base_with_embeddings.csv'
# Path to your new sample tickets CSV file
TICKETS_CSV_PATH = 'mock_data/sample_tickets.csv'

def setup_database():
    """Connects to the database, runs the schema, and ingests all mock data."""
    conn = None
    try:
        print("Connecting to the PostgreSQL database...")
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            host=DB_HOST, port=DB_PORT
        )
        cursor = conn.cursor()

        # --- 1. Execute the Schema to create/reset tables ---
        print("Executing schema.sql to create tables...")
        with open('schema.sql', 'r') as f:
            cursor.execute(f.read())
        conn.commit()
        print("Schema created successfully.")

        # --- 2. Ingest Knowledge Base from CSV ---
        print(f"Ingesting knowledge base from {KB_CSV_PATH}...")
        with open(KB_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header row
            insert_count = 0
            for row in reader:
                # IMPORTANT: Adjust these indices to match your CSV's column order
                # Example assumes: title, url, content, embedding_string
                title = row[0]
                url = row[1]
                content = row[2]
                embedding_str = row[3]
                
                cursor.execute(
                    "INSERT INTO pg_docs (title, url, content, embedding) VALUES (%s, %s, %s, %s);",
                    (title, url, content, embedding_str)
                )
                insert_count += 1
        conn.commit()
        print(f"Successfully ingested {insert_count} documents into pg_docs.")

        # --- 3. Ingest Sample Tickets from CSV ---
        print(f"Ingesting sample tickets from {TICKETS_CSV_PATH}...")
        with open(TICKETS_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip the header row ('ticket_id', 'user_id', etc.)
            insert_count = 0
            for row in reader:
                # The row is a list of strings: [ticket_id, user_id, description, log]
                cursor.execute(
                    "INSERT INTO tickets (ticket_id, user_id, description, log) VALUES (%s, %s, %s, %s);",
                    (row[0], row[1], row[2], row[3]) # Unpack the row directly
                )
                insert_count += 1
        conn.commit()
        print(f"Successfully ingested {insert_count} sample tickets.")

        print("\nDatabase setup is complete!")

    except FileNotFoundError as e:
        print(f"\n[ERROR] File not found: {e.filename}. Please make sure the CSV files exist at the correct paths.")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    setup_database()