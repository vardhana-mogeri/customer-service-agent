# AI Support Agent: Supporting Documentation

## 1. Executive Overview

The objective of this project was to develop a customer support agent to address user issues by leveraging a knowledge base and integrating with a system of record for ticket management. The core requirement was to build an AI agent capable of initiating a chat, retrieving ticket details provided by a customer, identifying relevant information from the knowledge base, and addressing the customer's concerns in a conversational manner.

This project delivers a stateful, context-aware agent that meets and significantly exceeds these original requirements. The final system not only retrieves specific tickets but also intelligently manages conversation history, allowing for natural follow-up questions. Critically, the tool has evolved beyond the initial scope by implementing several advanced features that dramatically enhance the user experience and automation potential. These include:

-   **Proactive Ticket Creation:** When the knowledge base is insufficient to solve a user's new issue, the agent proactively offers to create a ticket.
-   **Full Ticket History Listing:** Users can request a complete list of all their support tickets.
-   **Conversational Memory:** The agent remembers the immediate context of the conversation, allowing for intuitive follow-up questions.
-   **True Answer Synthesis:** The agent provides direct answers and solutions synthesized from the knowledge base, rather than simply returning links to documentation.

The agent's hybrid architecture, combining Retrieval-Augmented Generation (RAG) and Conversationally-Augmented Generation (CAG), provides a robust foundation for delivering instant, accurate, and contextually aware support.

## 2. Architectural Paradigm: A Hybrid RAG + CAG Model

To meet the project's requirements for both factual accuracy and conversational fluency, we implemented a hybrid architecture combining two key AI paradigms:

-   **Retrieval-Augmented Generation (RAG): The Agent's Factual Memory.** This directly addresses the requirement to "identify relevant information from knowledge base." RAG grounds the agent in facts by first retrieving relevant documents from our `pg_docs` vector database. The LLM is then instructed to synthesize its answer based only on this retrieved information. This prevents hallucination and ensures answers are backed by authoritative documentation.

-   **Conversationally-Augmented Generation (CAG): The Agent's Working Memory.** This addresses the requirement to "address customer concerns" in a natural, multi-turn chat. CAG provides the agent with the context of the current conversation through a graph-based history (`Apache AGE`) and the `active_ticket_id` state. This allows the agent to understand ambiguous follow-up questions like "what is the solution for that?".

By combining RAG and CAG, this agent is both factually accurate and conversationally intelligent.

## 3. Technology Stack Justification

The technology stack was chosen to create a simplified, powerful, and unified data backend, minimizing architectural complexity and operational overhead.

-   **Why PostgreSQL?**
    PostgreSQL was selected as the **unified data platform** for the entire project:
    -   **System of Record:** As a world-class RDBMS, it's the perfect choice for the `tickets` table.
    -   **Integrated Vector Database (`pgvector`):** This extension allows us to co-locate our knowledge base vectors alongside our structured ticket data, eliminating the need for a separate, dedicated vector database and simplifying the architecture.
    -   **Integrated Graph Database (`Apache AGE`):** This extension allows us to store conversation history as a graph directly within PostgreSQL, providing a scalable solution for the agent's memory without adding another database to the stack.

-   **Why the Rest of the Stack?**
    -   **Python:** The de facto language for AI/ML development.
    -   **Groq:** Chosen for its extremely low latency LPU™ Inference Engine, which is critical for a real-time chat application. The free tier's 30 RPM is sufficient for this prototype.
    -   **SentenceTransformers:** A high-performance, open-source library for creating text embeddings locally, avoiding API costs and dependencies.
    -   **Streamlit:** Selected for its ability to rapidly develop interactive user interfaces.

## 4. Core Logic and Orchestration (`agent.py`)

The `agent.py` script orchestrates the pipeline for each user message:

1.  **Intent Classification:** A fast LLM (`llama-3.1-8b-instant`) determines the user's primary goal.
2.  **Context Gathering:** The agent uses tools to fetch ticket details (System of Record) and performs a RAG retrieval from the `pg_docs` knowledge base.
3.  **Response Synthesis:** The complete context is sent to a powerful Synthesis LLM (`llama-3.3-70b-versatile`), which is governed by a robust system prompt to generate a helpful, conversational response.
4.  **Memory Update:** The turn is saved to the Apache AGE graph database.