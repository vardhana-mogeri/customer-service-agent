# llm_client.py

import groq
import os
import json

class LlmClient:
    """
    A client for interacting with the Groq API.
    This class is responsible for making the actual API calls to the LLMs.
    It is designed to be generic, taking prompts from the agent and returning
    the raw model output.
    """
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Groq API key is required.")
        self.client = groq.Groq(api_key=api_key)

    def generate_intent(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Uses the fast Llama 3 8B model for structured intent classification.

        Args:
            system_prompt: The "constitution" for the model (e.g., "You are a JSON expert...").
            user_prompt: The specific "command" for the model (e.g., "Analyze this query...").

        Returns:
            A dictionary containing the parsed JSON response from the model.
        """
        try:
            response = self.client.chat.completions.create(
                model="llama3-8b-8192",  # The fast model for classification
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
        """
        Uses the powerful Llama 3 70B model for synthesizing a response from context.

        Args:
            system_prompt: The persona and rules for the RAG response.
            user_prompt: The context and user query for the model to synthesize.

        Returns:
            A string containing the generated response.
        """
        try:
            response = self.client.chat.completions.create(
                model="llama3-70b-8192",  # The powerful model for synthesis
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # A little creativity, but keep it factual
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"An error occurred during response generation: {e}")
            return "I'm sorry, I encountered a technical error and couldn't process your request. Please try again."