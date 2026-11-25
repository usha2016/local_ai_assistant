# Local AI Assistant

A Python assistant that runs fully on my own computer, without internet.

## Features
- Time, date and calculator
- Notes and to-do list (saved in a JSON file)
- Built-in answers (SQL joins, JSON, Python)
- Local AI answers using Ollama (llama3.2)

## How it works
- Regex-based intent detection sends each command to the right function.
- Notes and tasks are stored in `assistant_data.json`.
- Unknown questions go to a local AI model through Ollama.
- If Ollama is not running, the assistant still works with its built-in features.

## Run
1. Install Python 3.
2. (Optional) Install Ollama and run `ollama pull llama3.2`.
3. Run: `python assistant.py`

## Tech
Python, regex, JSON, Ollama (local LLM)
