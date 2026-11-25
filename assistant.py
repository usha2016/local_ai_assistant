import ast
import datetime
import json
import operator
import os
import platform
import random
import re
import subprocess
import urllib.request

BOT_NAME = "Nova"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_data.json")
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


# ---------- storage ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"notes": [], "tasks": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------- safe calculator ----------
OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](safe_eval(node.operand))
    raise ValueError("unsupported expression")


# ---------- handlers ----------
def h_help(text, data):
    return (
        "I can do these:\n"
        "  - time / date\n"
        "  - calculate 12 * (3 + 4)   or   5 plus 3\n"
        "  - add note <text>  |  show notes\n"
        "  - add task <text>  |  show tasks  |  done <number>\n"
        "  - system info  |  joke\n"
        "  - ask anything else (needs Ollama for smart answers)\n"
        "  - bye"
    )


def h_greet(text, data):
    return random.choice(["Hello! How can I help?", "Hi there!", "Hey! What do you need?"])


def h_time(text, data):
    return "It's " + datetime.datetime.now().strftime("%I:%M %p")


def h_date(text, data):
    return "Today is " + datetime.datetime.now().strftime("%A, %d %B %Y")


def h_calc(text, data):
    expr = text.lower()
    for word, symbol in (("multiplied by", "*"), ("divided by", "/"), ("plus", "+"),
                         ("minus", "-"), ("times", "*"), ("power", "**"), ("^", "**")):
        expr = expr.replace(word, symbol)
    expr = re.sub(r"[^0-9+\-*/().% ]", "", expr).strip()
    try:
        result = safe_eval(ast.parse(expr, mode="eval").body)
        return f"{expr} = {result}"
    except Exception:
        return "Sorry, I couldn't calculate that. Try: calculate 12 * (3 + 4)"


def h_note_add(text, data):
    note = re.sub(r"^\s*(add\s+)?(a\s+)?note[:\s]*", "", text, flags=re.I).strip()
    if not note:
        return "What should the note say? Example: add note buy charger"
    data["notes"].append(note)
    save_data(data)
    return f"Note saved ({len(data['notes'])} total)."


def h_note_list(text, data):
    if not data["notes"]:
        return "You have no notes."
    return "Your notes:\n" + "\n".join(f"  {i}. {n}" for i, n in enumerate(data["notes"], 1))


def h_task_add(text, data):
    task = re.sub(r"^\s*(add\s+)?(a\s+)?(task|todo)[:\s]*", "", text, flags=re.I).strip()
    if not task:
        return "What is the task? Example: add task finish SQL practice"
    data["tasks"].append({"title": task, "done": False})
    save_data(data)
    return f"Task added ({len(data['tasks'])} total)."


def h_task_list(text, data):
    if not data["tasks"]:
        return "No tasks yet."
    lines = []
    for i, t in enumerate(data["tasks"], 1):
        mark = "x" if t["done"] else " "
        lines.append(f"  {i}. [{mark}] {t['title']}")
    return "Your tasks:\n" + "\n".join(lines)


def h_task_done(text, data):
    m = re.search(r"\d+", text)
    if not m:
        return "Tell me the task number. Example: done 1"
    idx = int(m.group()) - 1
    if 0 <= idx < len(data["tasks"]):
        data["tasks"][idx]["done"] = True
        save_data(data)
        return f"Marked task {idx + 1} as done."
    return "That task number doesn't exist."


def h_system(text, data):
    return (f"OS: {platform.system()} {platform.release()}\n"
            f"Python: {platform.python_version()}\n"
            f"Machine: {platform.machine()}")


def h_joke(text, data):
    return random.choice([
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "There are 10 kinds of people: those who understand binary and those who don't.",
        "A SQL query walks into a bar, sees two tables and asks: can I join you?",
    ])


# first matching pattern wins
ROUTES = [
    (r"\bhelp\b|\bwhat can you do\b", h_help),
    (r"\b(hi|hello|hey)\b", h_greet),
    (r"\b(show|list|view)\s+(my\s+)?notes\b", h_note_list),
    (r"\bnote\b", h_note_add),
    (r"\b(show|list|view)\s+(my\s+)?(tasks|todos)\b", h_task_list),
    (r"\b(task|todo)\b", h_task_add),
    (r"\b(done|complete|finished)\s+\d+", h_task_done),
    (r"\d\s*(\+|-|\*|/|\^|%|plus|minus|times|multiplied by|divided by|power)\s*\d|\bcalculate\b", h_calc),
    (r"\btime\b", h_time),
    (r"\bdate\b|\btoday\b|\bday\b", h_date),
    (r"\bsystem\b|\bcomputer info\b", h_system),
    (r"\bjoke\b", h_joke),
]


# ---------- built-in answers ----------
FAQ = {
    ("sql join", "joins"): (
        "SQL JOIN combines rows from two tables using a common column.\n"
        "  INNER JOIN: only matching rows from both tables.\n"
        "  LEFT JOIN: all rows from the left table + matches from the right.\n"
        "  RIGHT JOIN: all rows from the right table + matches from the left.\n"
        "  FULL JOIN: all rows from both tables.\n"
        "Example: SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id;"
    ),
    ("what is python",): "Python is a simple, popular programming language used for AI, data analysis and automation.",
    ("what is json", "json"): "JSON is a text format that stores data as key-value pairs. This project saves notes and tasks in JSON.",
    ("what is ollama", "ollama"): "Ollama is a tool that runs AI models (like llama3.2) locally on your own computer.",
    ("local ai assistant", "what are you"): "I am a local AI assistant. I run on your own computer, so your data stays private.",
}


def faq_answer(text):
    t = text.lower()
    for keys, answer in FAQ.items():
        if any(k in t for k in keys):
            return answer
    return None


# ---------- local LLM (Ollama) ----------
def ask_ollama_http(prompt):
    body = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    # ProxyHandler({}) = ignore Windows proxy, talk to Ollama directly
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=300) as resp:
            return json.loads(resp.read())["response"].strip()
    except Exception as e:
        print("Ollama HTTP error:", e)
        return None


def ask_ollama_cli(prompt):
    """Backup: use the same 'ollama run' command that works in the terminal."""
    try:
        r = subprocess.run(["ollama", "run", OLLAMA_MODEL, prompt],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", timeout=300)
        out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", r.stdout).strip()
        return out or None
    except Exception as e:
        print("Ollama CLI error:", e)
        return None


def ask_local_llm(prompt):
    print(f"{BOT_NAME}: Thinking... (first answer can take 1-3 minutes)")
    return ask_ollama_http(prompt) or ask_ollama_cli(prompt)


# ---------- main loop ----------
def respond(text, data):
    for pattern, handler in ROUTES:
        if re.search(pattern, text, flags=re.I):
            return handler(text, data)
    answer = faq_answer(text)
    if answer:
        return answer
    answer = ask_local_llm(text)
    if answer:
        return answer
    return "I don't know that yet. Type 'help' to see what I can do."


def main():
    data = load_data()
    print(f"{BOT_NAME}: Hi! I'm your local AI assistant. Type 'help' to see commands, 'bye' to quit.")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if re.search(r"\b(bye|exit|quit)\b", text, flags=re.I):
            print(f"{BOT_NAME}: Bye! See you soon.")
            break
        print(f"{BOT_NAME}: {respond(text, data)}")


if __name__ == "__main__":
    main() 