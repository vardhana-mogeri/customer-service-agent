# agent.py

# Standard library imports
import json
import os
from typing import Optional, Tuple

# Third-party imports
from dotenv import load_dotenv

# Local application/library specific imports
import database as db
from llm_client import LlmClient

# --- INITIALIZATION ---

# Load environment variables from .env file
load_dotenv()

# Load API key from environment variables for security.
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables.")

# Instantiate the LLM client once to be reused.
llm = LlmClient(api_key=groq_api_key)

# --- HELPER FUNCTION ---
def truncate_context_chunks(chunks: list[dict], max_length: int = 750) -> list[dict]:
    """Truncates the 'content' of each dictionary in a list to a maximum length.

    This function is used to shorten long text chunks, typically to ensure the total
    context sent to a language model fits within its context window or token limit.

    Args:
        chunks (list[dict]): A list of dictionaries, where each dictionary represents
            a document chunk and is expected to have a 'content' key.
        max_length (int, optional): The maximum number of characters to keep for
            the 'content' of each chunk. Defaults to 750.

    Returns:
        list[dict]: The list of chunks with their 'content' fields truncated
        where necessary. Note that the list is modified in-place.
    """
    for chunk in chunks:
        if 'content' in chunk and len(chunk['content']) > max_length:
            chunk['content'] = chunk['content'][:max_length] + "..."
    return chunks


# --- MAIN AGENT FUNCTION ---
def get_agent_response(
    user_id: str,
    session_id: str,
    user_query: str,
    active_ticket_id: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """Orchestrates the AI agent's response generation for a user query.

    This function serves as the central logic for the agent. It follows a multi-step
    process to understand the user, gather relevant information, and formulate a
    helpful, context-aware response.

    The process includes:
    1.  **Intent Classification:** An LLM call determines the user's goal (e.g.,
        asking about a ticket, creating a new one, general question).
    2.  **Tool-Based Context Gathering:** Based on the intent, it uses tools to
        fetch data from the database, such as specific ticket details, the user's
        entire ticket history, or conversation history.
    3.  **Contextual Search Query Refinement:** It improves the user's query to
        be more effective for vector database searches, especially for new issues
        or general questions.
    4.  **Retrieval-Augmented Generation (RAG):** It queries a vector database for
        relevant knowledge base articles, combines this with the tool-gathered
        context, and passes it to a final LLM call.
    5.  **Response Synthesis:** The final LLM call generates a user-facing response
        based on strict rules and all the provided context.
    6.  **Memory Update:** It saves the current user query and the agent's final
        response to the database to maintain conversation history.

    Args:
        user_id (str): The unique identifier for the user, used to fetch
            user-specific data like ticket history.
        session_id (str): The unique identifier for the current conversation
            session, used for retrieving conversation history.
        user_query (str): The raw text input from the user.
        active_ticket_id (Optional[str], optional): The ID of a ticket that is
            the current focus of the conversation. This maintains context across
            multiple turns. Defaults to None.

    Returns:
        Tuple[str, Optional[str]]: A tuple containing:
        - final_response (str): The generated, user-facing text response.
        - active_ticket_id_for_turn (Optional[str]): The ticket ID that should be
          considered active for the *next* turn in the conversation. This is used
          by the calling application to maintain state. It can be a newly
          identified, newly created, or previously active ticket ID.
    """
    
    # --- 1. ANALYZE USER INTENT ---
    intent_system_prompt = """
    You are an expert intent classification system. Your task is to analyze a user's query
    and output a JSON object with two keys: "intent" and "ticket_id".
    The "intent" can be one of:
    - "ticket_inquiry": The user is asking about a SPECIFIC ticket and provides a ticket ID.
    - "ticket_history_inquiry": The user is asking about their tickets in general (e.g., "what's my ticket status?", "my last ticket", "list all my tickets").
    - "ticket_creation_request": The user is explicitly asking to create a ticket (e.g., "can you create a ticket?", "yes, please create one").
    - "new_issue": The user is describing a new problem for the first time.
    - "general_question": The user is asking a general informational question.
    - "greeting": A simple greeting.

    The "ticket_id" should be the extracted ticket ID if the intent is "ticket_inquiry", otherwise it must be null.
    You must always respond with ONLY the JSON object and nothing else.
    """
    intent_user_prompt = f"Analyze the following user's query: \"{user_query}\""
    
    intent_data = llm.generate_intent(
        system_prompt=intent_system_prompt,
        user_prompt=intent_user_prompt
    )

    # --- 2. GATHER AND PROCESS CONTEXT FROM TOOLS ---
    
    context = ""
    search_query = user_query
    active_ticket_id_for_turn = active_ticket_id
    history = db.get_conversation_history(session_id)
    search_query_proactively_set = False

    if active_ticket_id_for_turn:
        ticket_details = db.get_ticket_details(active_ticket_id_for_turn)
        if ticket_details:
            context += f"CURRENT ACTIVE TICKET CONTEXT: {json.dumps(ticket_details)}\n"
            search_query = ticket_details.get('description', user_query)
            search_query_proactively_set = True
            print(f"INFO: Search query proactively set from active ticket {active_ticket_id_for_turn}: '{search_query}'")

    intent = intent_data.get("intent", "general_question")

    if intent == "ticket_inquiry":
        ticket_id = intent_data.get("ticket_id")
        if ticket_id:
            active_ticket_id_for_turn = ticket_id
            ticket_details = db.get_ticket_details(ticket_id)
            if ticket_details and ticket_details.get('user_id') == user_id:
                context += f"Ticket Information: {json.dumps(ticket_details)}\n"
                search_query = ticket_details['description']
                search_query_proactively_set = True
            elif not ticket_details:
                context += f"Ticket Information: No ticket found with ID {ticket_id}.\n"

    elif intent == "ticket_history_inquiry":
        user_tickets = db.get_tickets_by_user(user_id)
        if user_tickets:
            latest_ticket = user_tickets[0]
            context += f"The user's complete ticket history is: {json.dumps(user_tickets)}\n"
            active_ticket_id_for_turn = latest_ticket['ticket_id']
            search_query = latest_ticket['description']
            search_query_proactively_set = True
            print(f"INFO: Added full ticket history. Set active ticket to {active_ticket_id_for_turn} for next turn.")
        else:
            context += "User's Ticket History: This user has no tickets on record.\n"

    elif intent == "conversation_history_inquiry":
        # The history is already fetched at the beginning of the function.
        # We just need to add it to the context for the final LLM.
        if history:
            context += f"The user's recent conversation history is: {json.dumps(history)}\n"
        else:
            context += "There is no conversation history for this session yet.\n"
        # We don't need to do a RAG search for this, so we can clear the search query.
        search_query = ""
    
    elif intent == "ticket_creation_request":
        # Initialize final_response for this block
        final_response = ""
        
        # Step 1: Find the last thing the user said, which is the problem description.
        last_user_message = None
        if history:
            # Iterate backwards through history to find the last message from the 'user'
            # We skip the most recent one, which is the "create a ticket" request itself.
            for message in reversed(history):
                if message.get("author") == "user":
                    last_user_message = message.get("text")
                    break
        
        # Step 2: Check if we have a valid problem description to create a ticket from.
        if last_user_message:
            # Step 3: Perform the action - create the ticket in the database.
            new_ticket_id = db.create_ticket(user_id, last_user_message)
            
            # Step 4: Formulate a response based on whether the action was successful.
            if new_ticket_id:
                final_response = f"I've created a new ticket for you with ID: {new_ticket_id}. Our support team will look into it shortly."
                # Set the newly created ticket as the active one for the next turn.
                active_ticket_id_for_turn = new_ticket_id
            else:
                final_response = "I'm sorry, I encountered an error and couldn't create a ticket. Please try again."
        else:
            # This is a fallback if we can't find the context of the problem.
            final_response = "I'm sorry, I couldn't find a previous problem description to create a ticket from. Please describe your issue first."
            
        # --- IMPORTANT: We have handled the action, so update memory and return early ---
        db.add_message_to_graph(user_id, session_id, user_query, "user")
        db.add_message_to_graph(user_id, session_id, final_response, "agent")
        return final_response, active_ticket_id_for_turn

    elif intent in ["new_issue", "general_question"] and not search_query_proactively_set:
        query_refinement_system_prompt = "You are an expert at extracting concise technical search queries from user descriptions of problems. Respond with only the refined search query, no other text."
        query_refinement_user_prompt = f"Extract the core problem or keywords from the user's query: \"{user_query}\""
        refined_search_query = llm.generate_response(system_prompt=query_refinement_system_prompt, user_prompt=query_refinement_user_prompt).strip()
        if refined_search_query and refined_search_query.lower() != user_query.lower():
            search_query = refined_search_query
            print(f"INFO: Search query refined for '{intent}': '{search_query}'")

    if intent not in ["greeting"]:
        if history:
            context += f"Current Conversation History: {json.dumps(history)}\n"
        
        knowledge_chunks = db.query_vector_db(search_query, k=3)
        if knowledge_chunks:
            processed_chunks = truncate_context_chunks(knowledge_chunks)
            context += f"Relevant Knowledge Base Articles: {json.dumps(processed_chunks)}\n"
    
    MAX_TOKENS_SAFETY_MARGIN = 10000
    if len(context) > MAX_TOKENS_SAFETY_MARGIN:
        context = context[:MAX_TOKENS_SAFETY_MARGIN]

    # --- 3. SYNTHESIZE THE FINAL RESPONSE ---

    rag_system_prompt = """
    You are a helpful and personable expert PostgreSQL support agent. Your goal is to assist users by providing direct answers and solutions in a conversational way.

    Your primary task is to answer the user's query based *only* on the information provided in the Context.

    Here are your rules in order of priority:
    1.  **List All Tickets:** If the user asks for their tickets and the Context contains "The user's complete ticket history", you MUST list all the tickets provided. Start your response with a friendly phrase like "Here is a list of your tickets:" and format them clearly using a bulleted list.
    2.  **Summarize Conversation:** If the user asks about their past questions (e.g., "what did I ask?") and the Context contains "The user's recent conversation history", you MUST summarize the 'user' messages from that history.
    3.  **Summarize Single Tickets:** If the Context contains "Ticket Information" or "CURRENT ACTIVE TICKET CONTEXT", summarize the ticket's status and description for the user.
    4.  **Answer from Knowledge Base (Provide Solutions, Not Just Links):** If the Context contains "Relevant Knowledge Base Articles", your main goal is to act as an expert who has read them.
        - You MUST synthesize a direct answer by summarizing the key information and steps from the article 'content'.
        - Explain the potential solutions to the user in your own words.
        - **DO NOT just provide a list of links.** Your primary response must be the explanation.
        - You MAY include the URL at the end of your explanation as a reference for the user to learn more, but the answer itself comes first.
    5.  **Handle New Issues (Offer to Create a Ticket):** If the user describes a new issue and the provided articles do not seem to solve their specific problem, you MUST acknowledge this and then offer to create a ticket for them. For example: "I found some articles about server setup and authentication, but they might not solve your specific installation issue. Would you like me to create a ticket for this?"
    6.  **Fallback:** If, after following all the rules above, you genuinely cannot find any relevant information in the context to answer the query, you should say: "I'm sorry, I couldn't find specific information on that topic in my knowledge base."
    7.  **Style:** Never mention the words "Context" or "Knowledge Base" in your response. Be friendly and helpful.
    """
    rag_user_prompt = f"""Context:\n---\n{context}\n---\nUser's Query: {user_query}\n\nBased ONLY on the context provided, generate a helpful and concise response according to your rules."""
    
    final_response = llm.generate_response(system_prompt=rag_system_prompt, user_prompt=rag_user_prompt)

    # --- 4. UPDATE MEMORY ---
    db.add_message_to_graph(user_id, session_id, user_query, "user")
    db.add_message_to_graph(user_id, session_id, final_response, "agent")
    
    # --- 5. RETURN RESULTS ---
    return final_response, active_ticket_id_for_turn