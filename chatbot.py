import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types
from colorama import init, Fore, Style

# Ensure UTF-8 output in Windows terminal
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

# Initialize colorama for clean colored console output
init(autoreset=True)

def load_gemini_client():
    """Loads environment variables and initializes the Gemini API client."""
    load_dotenv()
    api_key = (
        os.getenv("gemini_api_key")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    if not api_key:
        print(f"{Fore.RED}[Error] API Key nahi mili! Kripya .env file me 'gemini_api_key' set karein.")
        sys.exit(1)

    return genai.Client(api_key=api_key)

# Aivora System Persona Instruction
AIVORA_SYSTEM_INSTRUCTION = """You are Aivora, a state-of-the-art, hyper-intelligent, and perceptive AI assistant.
You possess deep expertise in coding, science, philosophy, creative writing, daily productivity, mathematics, and problem-solving.
You are articulate, warm, insightful, and communicate fluently in both English and Hindi/Hinglish.
"""

def create_aivora_chat(client, model_name="gemma-4-26b-a4b-it"):
    return client.chats.create(
        model=model_name,
        config=types.GenerateContentConfig(
            system_instruction=AIVORA_SYSTEM_INSTRUCTION
        )
    )

def start_chat():
    """Main Aivora interactive loop with streaming responses and conversation memory."""
    client = load_gemini_client()
    
    # Priority model
    model_name = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")

    # Start a chat session with Aivora Persona
    chat = create_aivora_chat(client, model_name)

    print(Fore.CYAN + "=" * 65)
    print(Fore.MAGENTA + Style.BRIGHT + "   ✨ AIVORA // NEXT-GEN AI CONVERSATIONAL ASSISTANT ✨   ")
    print(Fore.CYAN + "=" * 65)
    print(Fore.YELLOW + f"• Active Engine: {model_name}")
    print(Fore.YELLOW + "• High-speed intelligence, coding, problem solving & dialogue ready.")
    print(Fore.YELLOW + "• Type 'exit' to quit | 'clear' to reset Aivora memory.")
    print(Fore.CYAN + "-" * 65 + "\n")

    while True:
        try:
            user_input = input(f"{Fore.GREEN}{Style.BRIGHT}You ❯ {Style.RESET_ALL}").strip()

            if not user_input:
                continue

            # Command to exit
            if user_input.lower() in ["exit", "quit", "q"]:
                print(f"\n{Fore.YELLOW}Astra session terminated. Goodbye! 👋\n")
                break

            # Command to clear chat history
            if user_input.lower() in ["clear", "reset"]:
                chat = create_astra_chat(client, model_name)
                print(f"\n{Fore.CYAN}✨ Astra context memory cleared! Starting fresh session.\n")
                continue

            # Print bot response with streaming effect
            print(f"{Fore.CYAN}{Style.BRIGHT}Astra ❯ {Style.RESET_ALL}", end="", flush=True)
            response_stream = chat.send_message_stream(user_input)

            for chunk in response_stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
            print("\n")

        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}Astra session interrupted. Goodbye! 👋\n")
            break
        except Exception as e:
            print(f"\n{Fore.RED}[Astra Engine Exception]: {e}\n")

if __name__ == "__main__":
    start_chat()

