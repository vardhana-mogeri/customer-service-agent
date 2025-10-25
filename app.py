# app.py
import streamlit as st
from agent import get_agent_response
import utils # For seeding data

st.title("PostgreSQL AI Support Agent")

# --- User Switching Logic ---
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

col1, col2 = st.columns(2)
with col1:
    if st.button("Switch to User 1 (Has History)"):
        st.session_state.current_user = 1
        st.session_state.session_id = "session_user_1" # A unique session ID
        if "messages" not in st.session_state:
            st.session_state.messages = []
        # Here you might load history from the DB, or just start fresh
        st.rerun()

with col2:
    if st.button("Switch to User 2 (New User)"):
        st.session_state.current_user = 2
        st.session_state.session_id = "session_user_2"
        st.session_state.messages = [] # Start with a clean slate
        st.rerun()

# --- Main Chat Interface ---
if st.session_state.current_user:
    st.header(f"Conversation with User {st.session_state.current_user}")

    # Initialize chat history for the session
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("How can I help you with PostgreSQL?"):
        # Add user message to session state and display
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = get_agent_response(
                    st.session_state.current_user,
                    st.session_state.session_id,
                    prompt
                )
                st.markdown(response)
        
        # Add agent response to session state
        st.session_state.messages.append({"role": "assistant", "content": response})
else:
    st.info("Please select a user to begin the chat.")