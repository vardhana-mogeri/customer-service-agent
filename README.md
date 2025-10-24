# Stateful AI Customer Support Agent Prototype

This project is a fully functional prototype of a stateful, context-aware AI customer support agent. It is designed to demonstrate an advanced, hybrid architecture that goes beyond simple Retrieval-Augmented Generation (RAG). The agent is grounded in a specific knowledge base (PostgreSQL documentation) and can manage conversational context and ticket history, simulating a real-world enterprise environment.

The primary goal is to showcase a system that can handle complex user interactions by maintaining state, retrieving specific knowledge, and interacting with a simulated System of Record (SoR).

### Key Features

*   **Hybrid RAG + CAG Architecture:**
    *   **Retrieval-Augmented Generation (RAG):** Uses `pgvector` to perform semantic search over a curated knowledge base, ensuring all informational responses are strictly grounded in facts and minimizing hallucinations.
    *   **Context-Aware Generation (CAG):** Leverages a graph database (`Apache AGE`) to maintain a stateful memory of the conversation, allowing the agent to understand follow-up questions and user history.
*   **System of Record (SoR) Integration:** Simulates a ticketing system (like Jira or Zendesk) where the agent can create, retrieve, and update support tickets stored in a relational table.
*   **Multi-User Session Management:** The Streamlit UI demonstrates the ability to manage separate conversation states and histories for different users.
*   **Strict Knowledge Scoping:** The agent's LLM is explicitly instructed to only synthesize answers from the context provided by its tools (RAG, CAG, SoR), demonstrating a safe and controlled AI implementation.

### Core Technologies

*   **Frontend:** Streamlit
*   **Orchestration:** Python
*   **LLM:** 
*   **Database:** PostgreSQL
*   **Vector Search (RAG):** `pgvector` extension
*   **Graph Memory (CAG):** `Apache AGE` extension
*   **Embeddings Model:** `all-MiniLM-L6-v2
