import json, requests, uuid, time, os, re
from datetime import datetime
from tqdm import tqdm
import hashlib

# --- CONFIGURATION ---
OLLAMA_API = "http://localhost:11435/api/generate"
MODEL = "qwen2.5-coder:32b" 
INPUT_FILE = "chat_history_52M.txt" 
OUTPUT_FILE = "refined_paths_5090.json"
CHUNK_SIZE = 12000 
SAVE_INTERVAL = 5  # Save after every 5 chunks

def call_ollama(prompt):
    """Robust wrapper for Ollama API calls."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 16384, # Leveraging 5090 VRAM
            "temperature": 0.1
        }
    }
    try:
        response = requests.post(OLLAMA_API, json=payload, timeout=120)
        return response.json().get('response', '')
    except Exception as e:
        print(f"\n[!] API Communication Error: {e}")
        return ""

def extract_from_chunk(text):
    """Extracts project nodes using double-braces to avoid f-string errors."""
    prompt = f"""
    Analyze the chat history. Extract project ideas, career milestones, or research goals.
    
    ### OUTPUT FORMAT:
    Return ONLY a valid JSON list of objects. No preamble.
    [ {{"title": "Name", "description": "Intent", "category": "AI/ML|Career|Personal", "value": 1-5}} ]
    
    TEXT:
    {text}
    """
    raw = call_ollama(prompt)
    try:
        # Regex surgically extracts the JSON list from any surrounding text
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except: pass
    return []

def verify_node(node, source_text):
    """Binary Auditor to ground extracted nodes in the source text."""
    prompt = f"Does the text below verify project '{node.get('title')}'? Answer ONLY 'YES' or 'NO'.\n\nTEXT: {source_text[:1500]}"
    res = call_ollama(prompt).upper()
    return "YES" in res

CHECKPOINT_FILE = "refinery_checkpoint.txt"

def process_history():
    all_extracted = []
    OVERLAP_SIZE = 1000 
    
    # --- RESUME LOGIC: LOAD EXISTING DATA ---
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try: all_extracted = json.load(f)
            except: all_extracted = []
    # --- CHECKPOINT LOGIC: FIND STARTING POSITION ---
    start_pos = 0
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as cf:
            try: start_pos = int(cf.read().strip())
            except: start_pos = 0

    file_size = os.path.getsize(INPUT_FILE)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        f.seek(start_pos) # JUMP TO LAST SAVED POSITION
        with tqdm(total=file_size, initial=start_pos, desc="Refining Ore", unit="char", colour="green") as pbar:
            leftover = ""
            while True:
                current_pos = f.tell() # MARK THE BYTE OFFSET
                raw_chunk = f.read(CHUNK_SIZE)
                if not raw_chunk: break
                
                chunk = leftover + raw_chunk
                results = extract_from_chunk(chunk)
                
                if results:
                    for item in results:
                        if isinstance(item, dict) and 'title' in item:
                            # --- DEDUPLICATION LOGIC: SHA256 FINGERPRINT ---
                            content_str = f"{item['title']}{item.get('description', '')}"
                            node_hash = hashlib.sha256(content_str.encode()).hexdigest()
                            
                            # Check if we've seen this specific idea before
                            if any(node.get('hash') == node_hash for node in all_extracted):
                                continue 

                            if verify_node(item, chunk):
                                print(f"\n[+] Verified Idea: {item['title']}")
                                item.update({
                                    "id": str(uuid.uuid4()),
                                    "hash": node_hash, # Store hash for future dedupe
                                    "status": "Staging",
                                    "source_context": chunk, 
                                    "createdAt": datetime.now().isoformat()
                                })
                                all_extracted.append(item)
                
                leftover = chunk[-OVERLAP_SIZE:]
                pbar.update(len(raw_chunk))

                # --- HARDENED SAVE: DATA + CHECKPOINT ---
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
                    json.dump(all_extracted, out, indent=2)
                with open(CHECKPOINT_FILE, 'w') as cf:
                    cf.write(str(current_pos))

    print(f"\n[SUCCESS] Refinery Complete. {len(all_extracted)} ideas staged.")

if __name__ == "__main__":
    process_history()