# Stateful AI Customer Support Agent Prototype

This project is a fully functional prototype of a stateful, context-aware AI customer support agent. It is designed to demonstrate an advanced, hybrid architecture that goes beyond simple Retrieval-Augmented Generation (RAG). The agent is grounded in a specific knowledge base (PostgreSQL documentation) and can manage conversational context and ticket history, simulating a real-world enterprise environment.

The primary goal is to showcase a system that can handle complex user interactions by maintaining state, retrieving specific knowledge, and interacting with a simulated System of Record (SoR).

### Key Features

*   **Hybrid RAG + CAG Architecture:**
    *   **Retrieval-Augmented Generation (RAG):** Uses `pgvector` to perform semantic search over a curated knowledge base, ensuring all informational responses are strictly grounded in facts.
    *   **Context-Aware Generation (CAG):** Leverages a graph database (`Apache AGE`) to maintain a stateful memory of the conversation, allowing the agent to understand follow-up questions.
*   **System of Record (SoR) Integration:** Simulates a ticketing system where the agent can create, retrieve, and list support tickets stored in a relational table.
*   **Multi-User Session Management:** The Streamlit UI demonstrates the ability to manage separate conversation states and histories for different users.
*   **Intelligent Answer Synthesis:** The agent provides direct answers and solutions, not just links, by synthesizing information from the knowledge base.

### Core Technologies

*   **Frontend:** Streamlit
*   **Orchestration:** Python 3.10
*   **LLM:** Groq API with `llama-3.1-8b-instant` (for Intent) and `llama-3.3-70b-versatile` (for Response)
*   **Database:** PostgreSQL (v15+)
*   **Vector Search (RAG):** `pgvector` extension
*   **Graph Memory (CAG):** `Apache AGE` extension
*   **Embeddings Model:** `all-MiniLM-L6-v2` (via SentenceTransformers)

---

## Getting Started

Follow these instructions to set up and run the project locally.

### Prerequisites

*   Python 3.10 or later
*   Git
*   A running instance of PostgreSQL (v15 or later) with the `pgvector` and `Apache AGE` extensions installed and loaded.

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd customer-support-agent
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**
    *   Create a copy of the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Open the `.env` file and fill in your specific credentials for your PostgreSQL database and your Groq API key.

5.  **Set up and Seed the Database:**
    *   First, ensure you have created a database in PostgreSQL with the name you specified in your `.env` file (e.g., `customer_support_kb`).
    *   Run the ingestion script. This single command will create the required tables (from `schema.sql`) and populate them with the mock data.
        ```bash
        python3 ingest_data.py
        ```

6.  **Run the Streamlit Application:**
    *   Use this command to run the app. It is important to use the `-m` flag to ensure it runs with the Python from your virtual environment.
        ```bash
        python3 -m streamlit run app.py
        ```
    *   Open your web browser and navigate to `http://localhost:8501`.

### Testing

This project includes a simple script to test the core RAG retrieval functionality. After setting up the database, you can run this script to validate that the vector search is working correctly.

```bash
python3 test_rag_retrieval.py
```
You can edit the `TEST_QUERY` variable inside the script to experiment with different searches.

### Project Structure

*   `app.py`: The main Streamlit application file that runs the user interface.
*   `agent.py`: The core "brain" of the agent, orchestrating the entire logic flow.
*   `database.py`: Contains all functions for interacting with the PostgreSQL database.
*   `llm_client.py`: A client for interacting with the Groq LLM API.
*   `ingest_data.py`: A one-time setup script to create the schema and load all mock data.
*   `schema.sql`: The SQL blueprint for creating all necessary database tables and extensions.
*   `test_rag_retrieval.py`: A utility script for testing RAG retrieval.
*   `mock_data/`: Contains the CSV files for the knowledge base and sample tickets.