import json, requests, os, hashlib, ctypes, time, re
from datetime import datetime
import tiktoken 

# --- CONFIGURATION ---
INPUT_FILE = "chat_history_52M.txt"
LEDGER_FILE = "ledger.json"
OUTPUT_FILE = "refined_paths_5090.json"
TOKEN_CHUNK_SIZE = 3000
TOKEN_OVERLAP = 300
enc = tiktoken.get_encoding("cl100k_base")

# --- THE MICTL-LITE SYSTEM PROMPT ---
SYSTEM_PROMPT = """
ROLE: High-Recall Extraction Engine for the Big-PDAT-Sorter.
TASK: Ingest text and extract "Atomic Semantic Nodes."
SCHEMA: Return ONLY a JSON object with a key "nodes" containing a list of:
{
  "title": "str (max 60 chars)",
  "path_type": "Primary|Sidequest|Risk|Dependency|Decision|Note",
  "summary": ["fact 1", "fact 2", "fact 3"],
  "source_refs": "direct quote or snippet",
  "next_action": "verb-driven concrete step",
  "confidence": 0.0-1.0
}
CONSTRAINTS: No conversational fluff. If nothing found, return {"nodes": []}.
"""

def stay_awake():
    """Communicates with kernel32.dll to prevent Windows Sleep."""
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 | 0x00000040)

def get_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

def get_deterministic_id(title, path_type):
    """Priority #4: Deterministic content-based hashing for deduplication."""
    clean = f"{title.lower().strip()}{path_type.lower().strip()}"
    return hashlib.sha256(clean.encode()).hexdigest()[:12]

def call_ollama(model, prompt, is_json=True):
    payload = {
        "model": model, "prompt": prompt, "stream": False,
        "options": {"num_ctx": 16384, "temperature": 0.1},
        "format": "json" if is_json else ""
    }
    try:
        r = requests.post("http://localhost:11435/api/generate", json=payload, timeout=180)
        return r.json().get('response', '')
    except Exception as e:
        print(f"API Error ({model}): {e}")
        return ""

def verify_grounding(node, chunk_text):
    """Llama 3 Binary Auditor: Strictly checks substring support."""
    prompt = f"[AUDITOR] Does this node exist in the source text?\nNODE: {node['title']}\nSUMMARY: {node['summary']}\nSOURCE: {chunk_text[:2000]}\nRespond ONLY with JSON: {{\"pass\": true/false}}"
    res_raw = call_ollama("llama3.1:8b", prompt)
    try:
        return json.loads(res_raw).get("pass", False)
    except: return False

def refinery_loop():
    stay_awake()
    
    # Initialize Ledger
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r') as f: ledger = json.load(f)
    else: ledger = {"processed_chunks": [], "emitted_ids": []}

    # Load Source File
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        full_text = f.read()
        tokens = enc.encode(full_text, disallowed_special=())

    print(f"Distillation Started. Processing {len(tokens)} tokens...")

    

    for i in range(0, len(tokens), TOKEN_CHUNK_SIZE - TOKEN_OVERLAP):
        chunk_tokens = tokens[i : i + TOKEN_CHUNK_SIZE]
        chunk_text = enc.decode(chunk_tokens)
        chunk_hash = get_hash(chunk_text)

        # SKIP IF ALREADY DONE (Idempotency)
        if chunk_hash in ledger["processed_chunks"]:
            continue

        print(f"Milling Chunk: {chunk_hash[:8]} | Progress: {round((i/len(tokens))*100, 2)}%")
        
        # 1. QWEN EXTRACTION
        qwen_prompt = f"{SYSTEM_PROMPT}\n\nTEXT CHUNK:\n{chunk_text}"
        candidates_raw = call_ollama("qwen2.5-coder:32b", qwen_prompt)
        
        try:
            candidates = json.loads(candidates_raw).get('nodes', [])
        except:
            print("  ! Format Error in Qwen output, skipping chunk.")
            continue

        

        # 2. LLAMA VERIFICATION & LEDGER UPDATE
        for node in candidates:
            node_id = get_deterministic_id(node.get('title', ''), node.get('path_type', ''))
            
            if node_id in ledger["emitted_ids"]:
                continue

            if verify_grounding(node, chunk_text):
                node['id'] = node_id
                node['timestamp'] = datetime.now().isoformat()
                
                # Append to Output (JSONL style for safety)
                with open(OUTPUT_FILE, 'a') as out:
                    out.write(json.dumps(node) + "\n")
                
                ledger["emitted_ids"].append(node_id)

        # 3. SAVE STATE
        ledger["processed_chunks"].append(chunk_hash)
        with open(LEDGER_FILE, 'w') as lf:
            json.dump(ledger, lf)

    print("--- DISTILLATION COMPLETE ---")

if __name__ == "__main__":
    try:
        refinery_loop()
    finally:
        # Release Kernel Lock (Allow sleep again)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)