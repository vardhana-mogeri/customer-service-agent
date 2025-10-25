# # agent.py
# import database as db
# import json
# from llm_client import LlmClient

# llm = LlmClient(api_key="...")

# def get_agent_response(user_id, session_id, user_query):
#     # 1. Analyze user intent (a small LLM call)
#     intent_prompt = f"""
#     Analyze the user's query: "{user_query}"
#     Classify the intent:
#     - "ticket_inquiry": User is asking about an existing ticket (e.g., "any update on T-123?").
#     - "new_issue": User is describing a new problem.
#     - "general_question": User is asking a question that can be answered by the knowledge base.

#     If the intent is 'ticket_inquiry', extract the ticket ID.
#     Respond in JSON format. Example: {{"intent": "ticket_inquiry", "ticket_id": "T-123"}}
#     """
#     intent_response = llm.generate(intent_prompt) # This would be a JSON object
#     intent_data = json.loads(intent_response)

#     context = ""

#     # 2. Use tools based on intent (Gathering Context)
#     if intent_data["intent"] == "ticket_inquiry":
#         ticket_id = intent_data.get("ticket_id")
#         if ticket_id:
#             ticket_details = db.get_ticket_details(ticket_id)
#             context += f"Ticket Information: {ticket_details}\n"
#             # Also get related conversation history
#             history = db.get_conversation_history(user_id, session_id)
#             context += f"Conversation History: {history}\n"

#     # For any intent that isn't just a simple greeting, search the KB
#     if intent_data["intent"] in ["new_issue", "general_question", "ticket_inquiry"]:
#         knowledge_chunks = db.query_vector_db(user_query)
#         context += f"Relevant Knowledge Base Articles: {knowledge_chunks}\n"

#     # 3. Synthesize the final response (the RAG part)
#     final_prompt = f"""
#     You are a helpful customer support agent for PostgreSQL.
#     Your knowledge is STRICTLY limited to the provided context. Do not answer any question if the answer is not in the context.
#     If you don't know the answer, say "I'm sorry, that information is not in my knowledge base."

#     Context:
#     {context}

#     User's Query: {user_query}

#     Based ONLY on the context provided, generate a helpful and concise response.
#     If the user has a new issue that the knowledge base cannot solve, offer to create a ticket for them.
#     """
#     final_response = llm.generate(final_prompt)

#     # 4. Update memory (the CAG part)
#     db.add_message_to_graph(user_id, session_id, user_query, "user")
#     db.add_message_to_graph(user_id, session_id, final_response, "agent")
    
#     # You could also add logic here to create/update tickets if needed
#     # e.g., if the user accepts the offer to create a ticket.

#     return final_response

# agent.py (Corrected and Improved)

import database as db
import json
import os
from llm_client import LlmClient # Assuming llm_client.py exists

# Best Practice: Load API key from environment variables
# Make sure you have a .env file with GROQ_API_KEY="your-key"
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables.")

llm = LlmClient(api_key=groq_api_key)

def get_agent_response(user_id, session_id, user_query):
    # --- 1. Analyze user intent (using the two-prompt system) ---
    
    # The "Constitution" for the intent model
    intent_system_prompt = """
    You are an expert intent classification system. Your task is to analyze a user's query
    and output a JSON object with two keys: "intent" and "ticket_id".
    The "intent" can be one of: "ticket_inquiry", "new_issue", "general_question", "greeting".
    The "ticket_id" should be the extracted ticket ID if the intent is "ticket_inquiry", otherwise it must be null.
    You must always respond with ONLY the JSON object and nothing else.
    """
    
    # The "Command" for the intent model
    intent_user_prompt = f"""
    Analyze the following user's query: "{user_query}"
    """
    
    # The LLM call is now cleaner and more reliable
    intent_data = llm.generate_intent(
        system_prompt=intent_system_prompt,
        user_prompt=intent_user_prompt
    )

    context = ""

    # --- 2. Use tools based on intent (Gathering Context) ---
    intent = intent_data.get("intent", "general_question") # Default to general_question

    if intent == "ticket_inquiry":
        ticket_id = intent_data.get("ticket_id")
        if ticket_id:
            ticket_details = db.get_ticket_details(ticket_id)
            if ticket_details:
                context += f"Ticket Information: {json.dumps(ticket_details)}\n"
            
            # Also get related conversation history for the ticket
            history = db.get_conversation_history(session_id)
            context += f"Current Conversation History: {json.dumps(history)}\n"

    # For any intent that isn't just a simple greeting, search the KB
    if intent in ["new_issue", "general_question", "ticket_inquiry"]:
        knowledge_chunks = db.query_vector_db(user_query, k=3) # Get top 3 chunks
        context += f"Relevant Knowledge Base Articles: {json.dumps(knowledge_chunks)}\n"

    # --- 3. Synthesize the final response (the RAG part) ---
    
    # The "Constitution" for the response model
    rag_system_prompt = """
    You are a helpful and concise customer support agent for PostgreSQL.
    Your knowledge is STRICTLY limited to the information provided in the 'Context' section.
    Do not answer any question if the answer is not present in the context.
    If you do not know the answer based on the context, you MUST say "I'm sorry, that information is not in my knowledge base."
    Never mention the context or knowledge base directly in your response. Just answer the user's query.
    """
    
    # The "Command" for the response model
    rag_user_prompt = f"""
    Context:
    ---
    {context}
    ---
    User's Query: {user_query}

    Based ONLY on the context provided, generate a helpful and concise response.
    If the context suggests the user has a new issue that cannot be solved with the provided articles, offer to create a ticket for them.
    """
    
    final_response = llm.generate_response(
        system_prompt=rag_system_prompt,
        user_prompt=rag_user_prompt
    )

    # --- 4. Update memory (the CAG part) ---
    db.add_message_to_graph(user_id, session_id, user_query, "user")
    db.add_message_to_graph(user_id, session_id, final_response, "agent")
    
    return final_response