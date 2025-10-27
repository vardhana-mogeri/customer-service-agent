# app.py

import streamlit as st
from agent import get_agent_response

st.title("PostgreSQL AI Support Agent")

# --- Session State Initialization ---
# Initialize all session state variables at the top to avoid errors.

if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# Initialize the "working memory" for the active ticket.
if 'active_ticket_id' not in st.session_state:
    st.session_state.active_ticket_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- User Switching Logic ---
col1, col2 = st.columns(2)
with col1:
    if st.button("Switch to User 1 (Has History)"):
        st.session_state.current_user = 1
        # A unique session ID
        st.session_state.session_id = "session_user_1"
        # Reset chat history 
        st.session_state.messages = [] 
        # Reset the active ticket when switching users to prevent context leaks.
        st.session_state.active_ticket_id = None
        st.rerun()

with col2:
    if st.button("Switch to User 2 (New User)"):
        st.session_state.current_user = 2
        st.session_state.session_id = "session_user_2"
        # Reset chat history
        st.session_state.messages = [] 
        # Reset the active ticket here as well.
        st.session_state.active_ticket_id = None
        st.rerun()

# --- Main Chat Interface ---
if st.session_state.current_user:
    st.header(f"Conversation with User {st.session_state.current_user}")

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("How can I help you with PostgreSQL?"):
        # Add user message to session state and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response, new_active_ticket_id = get_agent_response(
                    st.session_state.current_user,
                    st.session_state.session_id,
                    prompt,
                    st.session_state.active_ticket_id # Pass the current state IN
                )
                
                # This is how the agent maintains its "working memory" for the next turn.
                st.session_state.active_ticket_id = new_active_ticket_id
                
                st.markdown(response)
        
        # Add agent response to session state
        st.session_state.messages.append({"role": "assistant", "content": response})
else:
    st.info("Please select a user to begin the chat.")