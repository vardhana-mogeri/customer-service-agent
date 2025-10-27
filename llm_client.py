# llm_client.py

import groq
import json
from typing import Dict, Any

class LlmClient:
    """A client for interacting with the Groq API, optimized for a two-model strategy.

    This class serves as an abstraction layer over the raw `groq.Groq` client,
    tailoring API calls for specific tasks within the conversational agent. It is
    responsible for:
    1.  Making the actual API calls to the Large Language Models (LLMs).
    2.  Directing requests to the appropriate model (a fast, small model for
        structured tasks, and a powerful, large model for response generation).
    3.  Handling potential errors, such as API failures or invalid JSON output,
        and providing safe fallback responses.
    """
    def __init__(self, api_key: str):
        """Initializes the LlmClient with the necessary API key.

        Args:
            api_key (str): The Groq API key used to authenticate with the service.

        Raises:
            ValueError: If the provided `api_key` is empty or None.
        """
        if not api_key:
            raise ValueError("Groq API key is required.")
        self.client = groq.Groq(api_key=api_key)

    def generate_intent(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Performs structured intent classification using a fast, small LLM.

        This method is optimized for speed and accuracy in a classification task.
        It uses Groq's `llama-3.1-8b-instant` model with forced JSON output and zero
        temperature to get a deterministic, machine-readable classification of the
        user's intent.

        If the LLM fails to produce valid JSON or if an API error occurs, this
        method provides a safe fallback response to prevent the agent from crashing.

        Args:
            system_prompt (str): The system prompt that defines the rules and
                expected JSON schema for the classification task.
            user_prompt (str): The user's query that needs to be classified.

        Returns:
            Dict[str, Any]: A dictionary containing the classified intent and any
            extracted entities (e.g., 'ticket_id'). On failure, returns a default
            dictionary: `{"intent": "general_question", "ticket_id": None}`.
        """
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",  # The fast model for classification
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0  # No creativity needed for classification
            )
            return json.loads(response.choices[0].message.content)
        
        except json.JSONDecodeError:
            print("Warning: LLM failed to produce valid JSON for intent classification.")
            # Fallback to a safe default if the model messes up the JSON
            return {"intent": "general_question", "ticket_id": None}
        except Exception as e:
            print(f"An error occurred during intent generation: {e}")
            return {"intent": "general_question", "ticket_id": None}


    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generates a conversational response using a powerful, large LLM.

        This method is designed for high-quality, context-aware response synthesis.
        It uses Groq's `llama-3.3-70b-versatile` model, which has strong reasoning
        capabilities, to generate a human-like response based on the provided
        context and instructions in the prompts.

        If any API error occurs, it returns a user-friendly error message to be
        displayed directly in the chat interface.

        Args:
            system_prompt (str): The system prompt that defines the agent's persona,
                rules, and instructions for how to use the provided context.
            user_prompt (str): The complete context (e.g., ticket data, knowledge
                base articles, conversation history) and the user's original query.

        Returns:
            str: A string containing the generated conversational response.
            On failure, returns a generic error message for the user.
        """
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # The powerful model for synthesis
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # A little creativity, but keeping it factual
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"An error occurred during response generation: {e}")
            return "I'm sorry, I encountered a technical error and couldn't process your request. Please try again."