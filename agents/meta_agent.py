import os
import requests
import logging

class MetaAgent:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    
    def ask_llm(self, prompt: str, model: str = "gpt-oss-20b") -> str:
        """
        Sends a prompt to the specified Ollama model and returns the response.
        Defaults to 'gpt-oss-20b'.
        """
        try:
            # Set the default model from environment variables if not provided
            default_model = os.getenv("DEFAULT_MODEL", "gpt-oss-20b")
            model_to_use = model if model != "gpt-oss-20b" else default_model

            logging.info(f"Sending prompt to Ollama model '{model_to_use}': {prompt}")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model_to_use,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60 # Add a timeout for robustness
            )
            response.raise_for_status() # Raise an exception for bad status codes
            
            response_json = response.json()
            logging.info(f"Received response from Ollama: {response_json.get('response')}")
            
            return response_json.get("response", "Error: No response field in JSON.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Ollama API request failed: {e}")
            return f"Error: Could not connect to Ollama at {self.ollama_url}."
        except Exception as e:
            logging.error(f"An unexpected error occurred in MetaAgent: {e}")
            return "Error: An unexpected error occurred."

if __name__ == '__main__':
    # Simple test case for direct execution
    logging.basicConfig(level=logging.INFO)
    agent = MetaAgent()
    test_prompt = "Explain the concept of a 'meta-agent' in one sentence."
    print(f"Testing MetaAgent with prompt: '{test_prompt}'")
    response = agent.ask_llm(test_prompt)
    print(f"Response: {response}")
