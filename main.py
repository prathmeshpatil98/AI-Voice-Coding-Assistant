import os
import json
import signal
import time
from groq import Groq
from dotenv import load_dotenv
import speech_recognition as sr
import sounddevice as sd
import numpy as np
from TTS.api import TTS

from prompts import SYSTEM_PROMPT
from tools import (
    run_command,
    create_folder,
    write_file,
    read_file,
    list_files,
    run_server,
    stop_servers,
    get_current_directory,
    find_files,
    check_port,
)

load_dotenv()
client = Groq()

# Load TTS model (Coqui TTS)
tts_model = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)

# Text-to-Speech using Coqui TTS
def tts(text: str):
    print("🗣️ Speaking:", text)
    try:
        wav = tts_model.tts(text)
        sd.play(np.array(wav), samplerate=tts_model.synthesizer.output_sample_rate)
        sd.wait()
    except Exception as e:
        print(f"❌ TTS Error: {e}")

# Global variables for process management
running_processes = []
context_summary = ""

# ---------- CONTEXT MANAGEMENT ----------
def should_summarize_context(messages):
    """Check if context should be summarized"""
    total_tokens = sum(len(msg["content"]) for msg in messages)
    return total_tokens > 15000  # Approximate token limit

def summarize_context(messages):
    """Summarize conversation context"""
    try:
        # Keep system prompt and recent messages
        system_msg = messages[0]
        recent_messages = messages[-10:]  # Keep last 10 messages
        
        # Summarize middle messages
        middle_messages = messages[1:-10] if len(messages) > 11 else []
        
        if middle_messages:
            summary_prompt = """Summarize the following conversation between a user and a coding assistant. 
            Focus on: 1) What project was built, 2) Key features implemented, 3) Current state of the project.
            Keep it concise but informative."""
            
            summary_content = "\n".join([msg["content"] for msg in middle_messages])
            
            summary_response = client.chat.completions.create(
                model="llama3-8b-8192",  # Use cheaper model for summarization
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": summary_content}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            summary = summary_response.choices[0].message.content
            summary_msg = {"role": "system", "content": f"CONTEXT SUMMARY: {summary}"}
            
            return [system_msg, summary_msg] + recent_messages
        
        return messages
    except Exception as e:
        print(f"Error summarizing context: {e}")
        return messages

# ---------- ENHANCED TOOL MAPPING ----------
def safe_tool_call(tool_func, tool_input=None):
    try:
        # Some tools may not require input
        if tool_input is not None and tool_input != "":
            return tool_func(tool_input)
        else:
            return tool_func() if callable(tool_func) else None
    except Exception as e:
        print(f"[LOG] Tool error: {e}")  # Only log for debugging, not shown to user
        return None

available_tools = {
    "run_command": run_command,
    "create_folder": create_folder,
    "write_file": write_file,
    "read_file": read_file,
    "list_files": list_files,
    "run_server": run_server,
    "stop_servers": stop_servers,
    "get_current_directory": get_current_directory,
    "find_files": find_files,
    "check_port": check_port,
}

# ---------- MAIN LOOP WITH ENHANCEMENTS ----------
def main():
    global context_summary
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    r = sr.Recognizer()
    tts("Hey Prathmesh! What type of code would you like to create? Just tell me in your own words.")

    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n Shutting down gracefully...")
        stop_servers()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            with sr.Microphone() as source:
                print("\n Listening...")
                r.adjust_for_ambient_noise(source)
                audio = r.listen(source)
            
            try:
                user_input = r.recognize_google(audio)
                print(f"You said: {user_input}")
            except sr.UnknownValueError:
                tts("Sorry, I didn't catch that. Could you please repeat?")
                continue
            except sr.RequestError as e:
                tts("Sorry, there was a problem with the speech service. Please try again.")
                continue

            if user_input.lower() in ["exit", "quit"]:
                stop_servers()
                tts("Goodbye! Have a great day.")
                break

            # Check if context should be summarized
            if should_summarize_context(messages):
                print(" Summarizing context to improve performance...")
                messages = summarize_context(messages)
            messages.append({"role": "user", "content": user_input})

            # Main conversation loop
            while True:
                for attempt in range(3):  # Increased retry attempts
                    try:
                        response = client.chat.completions.create(
                            model="meta-llama/llama-4-scout-17b-16e-instruct",
                            response_format={"type": "json_object"},
                            messages=messages,
                            temperature=0.3,
                            max_tokens=2000
                        )
                        reply = response.choices[0].message.content
                        print(f"DEBUG: Raw Groq Reply: {reply}") # Added for debugging
                        parsed = json.loads(reply)
                        print(f"DEBUG: Parsed Groq Reply: {parsed}") # Added for debugging
                        break
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON parsing error (attempt {attempt + 1}): {e}")
                        if attempt == 2:
                            tts("Sorry, I had trouble understanding my own response. Let's try again.")
                            break
                        time.sleep(1)
                    except Exception as e:
                        print(f"⚠️ API error (attempt {attempt + 1}): {e}")
                        if attempt == 2:
                            tts("Sorry, something went wrong. Let's try again.")
                            break
                        time.sleep(2)
                else:
                    break

                # Only speak and print friendly, natural language
                step = parsed.get("step")
                if step == "plan":
                    tts(parsed['content'])
                    continue
                elif step == "action":
                    tool_name = parsed.get("tool")
                    tool_input = parsed.get("input")
                    if tool_name not in available_tools:
                        tts(f"Sorry, I don't know how to do that yet.")
                        break
                    # Run tool quietly
                    result = safe_tool_call(available_tools[tool_name], tool_input)
                    # Friendly summary for user
                    if tool_name == "create_folder":
                        tts("I've created your project folder. What would you like to do next?")
                    elif tool_name == "write_file":
                        tts("I've added or updated a file for you.")
                    elif tool_name == "run_server":
                        tts("Your application is now running on localhost. You can open it in your browser.")
                    elif tool_name == "stop_servers":
                        tts("I've stopped all running applications for you.")
                    elif tool_name == "get_current_directory":
                        tts("I'm working in your project folder.")
                    else:
                        tts("Done! What would you like next?")
                    messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "step": "tool_output",
                            "tool": tool_name,
                            "input": tool_input,
                            "output": "success"
                        })
                    })
                    continue
                elif step == "observe":
                    tts(parsed['content'])
                    continue
                elif step == "complete":
                    tts(parsed['content'])
                    break
                else:
                    tts("I'm ready for your next request.")
                    break
        except KeyboardInterrupt:
            stop_servers()
            tts("Goodbye! Have a great day.")
            break
        except Exception:
            tts("Sorry, something went wrong. Let's try again.")
            continue

if __name__ == "__main__":
    main()
