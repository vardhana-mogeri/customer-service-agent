# utils.py
import database as db

if __name__ == "__main__":
    print("Attempting to seed data for User 1...")
    
    # --- Seeding Ticket Data ---
    print("\nStep 1: Seeding ticket data...")
    ticket_seeded = db.create_or_update_ticket(
        ticket_id="T-007", 
        user_id=1, 
        description="Client connections are failing with 'FATAL: password authentication failed'.",
        log="Initial report. User has confirmed their password is correct."
    )
    
    if not ticket_seeded:
        print("\nFATAL: Failed to seed ticket data. Aborting.")
        exit(1) # Exit the script with an error code

    # --- Seeding Conversation History ---
    print("\nStep 2: Seeding conversation history...")
    user_id = 1
    session_id = "session_user_1"
    messages = [
        {"author": "user", "text": "Hi, I'm having trouble connecting to my database."},
        {"author": "agent", "text": "I can help with that. What is the exact error message you are seeing?"},
        {"author": "user", "text": "It says 'FATAL: password authentication failed'."}
    ]
    
    all_messages_seeded = True
    for msg in messages:
        print(f"  - Seeding message from {msg['author']}...")
        success = db.add_message_to_graph(user_id, session_id, msg["text"], msg["author"])
        if not success:
            print(f"  - FAILED to seed message from {msg['author']}.")
            all_messages_seeded = False
            break # Stop trying to seed messages if one fails
    
    if not all_messages_seeded:
        print("\nFATAL: Failed to seed conversation history. Aborting.")
        exit(1)

    print("\n Success! Demo data for User 1 has been seeded correctly.")