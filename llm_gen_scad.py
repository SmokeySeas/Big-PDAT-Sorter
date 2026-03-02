"""
llm_gen_scad.py — Ollama LLM wrapper for OpenSCAD code generation.

Describe geometry in natural language → LLM generates .scad code →
OpenSCAD validates and exports STL.

Usage:
    python llm_gen_scad.py "A plate 100x60x8mm with two M6 holes 70mm apart"
    python llm_gen_scad.py --modify base_jig_real.scad "make the handle taller"
    python llm_gen_scad.py --interactive
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

try:
    import requests

    def _post_json(url, payload, timeout):
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

except ImportError:
    import urllib.request
    import urllib.error

    def _post_json(url, payload, timeout):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


# --- Constants ---
OLLAMA_URL = "http://localhost:11434"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_RETRIES = 3
OPENSCAD_EXE = "openscad"
OPENSCAD_TIMEOUT = 120


def _get_json(url, timeout):
    """GET request that works with both requests and urllib."""
    try:
        import requests as _req
        resp = _req.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except ImportError:
        import urllib.request
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def get_default_model(base_url: str = OLLAMA_URL) -> str:
    """Auto-detect the first available model from Ollama."""
    try:
        result = _get_json(f"{base_url}/api/tags", timeout=5)
        models = result.get("models", [])
        if models:
            return models[0]["name"]
    except Exception:
        pass
    return "qwen2.5:14b"  # fallback if Ollama isn't reachable


def list_available_models(base_url: str = OLLAMA_URL) -> list[str]:
    """List all models currently downloaded in Ollama."""
    try:
        result = _get_json(f"{base_url}/api/tags", timeout=5)
        return [m["name"] for m in result.get("models", [])]
    except Exception:
        return []

SCAD_SYNTAX_REFERENCE = textwrap.dedent("""\
    ## OpenSCAD Quick Reference

    ### Primitives
    cube([x, y, z]);                    // box
    cube([x, y, z], center=true);       // centered box
    cylinder(h=H, d=D);                 // cylinder by diameter
    cylinder(h=H, r=R);                 // cylinder by radius
    cylinder(h=H, d1=D1, d2=D2);       // cone/taper
    sphere(d=D);                        // sphere

    ### Transforms
    translate([x, y, z]) child();
    rotate([rx, ry, rz]) child();
    scale([sx, sy, sz]) child();
    mirror([1, 0, 0]) child();

    ### Boolean Operations
    difference() { base(); cut1(); cut2(); }   // subtract 2..N from 1st
    union() { a(); b(); }                      // combine
    intersection() { a(); b(); }               // overlap only

    ### Extrusion
    linear_extrude(height=H) 2d_shape();
    rotate_extrude() 2d_shape();

    ### Text
    linear_extrude(height=1.5)
        text("LABEL", size=6, halign="center", font="Liberation Sans:style=Bold");

    ### Modules (reusable geometry)
    module my_part(x, y, d) {
        translate([x, y, 0]) cylinder(h=10, d=d);
    }
    my_part(20, 30, 8);   // call it

    ### Variables and Arrays
    width = 100;
    holes = [[10,10,6], [50,10,8], [30,40,6]];
    for (h = holes) {
        translate([h[0], h[1], -1]) cylinder(h=12, d=h[2], $fn=64);
    }

    ### Resolution
    $fn = 64;   // smooth circles (set at top of file)

    ### Common Pitfalls
    - Every statement ends with a semicolon
    - Arrays use square brackets: [1, 2, 3] not (1, 2, 3)
    - difference() subtracts children 2..N FROM child 1 (first child is the base)
    - for loops generate geometry, they are NOT imperative loops
    - Use d= for diameter OR r= for radius, never both
    - Holes need to extend slightly beyond surfaces (-1 offset, +2 height) to avoid z-fighting
    - CRITICAL: OpenSCAD does NOT support destructuring in for loops!
      WRONG: for ([x, y] = [[1,2],[3,4]]) ...
      RIGHT: for (p = [[1,2],[3,4]]) { translate([p[0], p[1], 0]) ... }
    - CRITICAL: text() is a 2D operation. To emboss text on a 3D face:
      translate([x, y, z]) rotate([90, 0, 0])
          linear_extrude(height=1.5)
              text("LABEL", size=5, halign="center");
""")


def build_system_prompt(root: Path) -> str:
    """Build the system prompt with syntax reference and template examples."""
    parts = [
        "You are an OpenSCAD code generator for manufacturing jig design.",
        "You output ONLY valid OpenSCAD code inside a single ```openscad code block.",
        "Do not include explanatory text outside the code block.",
        "The code must be a complete, self-contained .scad file that OpenSCAD can render to STL.",
        "Do NOT use include or use statements — all code must be in one file.",
        "",
        SCAD_SYNTAX_REFERENCE,
    ]

    # Load template examples from disk if available
    example_template = root / "base_jig_pads.scad"
    if example_template.exists():
        code = example_template.read_text(encoding="utf-8")
        # Strip the include line since we want self-contained output
        code_stripped = "\n".join(
            line for line in code.splitlines()
            if not line.strip().startswith("include")
        )
        parts.append("## Example: Simple Jig Template")
        parts.append(f"```openscad\n{code_stripped}\n```")
        parts.append("")

    example_data = root / "generated" / "jig_data_real.scad"
    if example_data.exists():
        data = example_data.read_text(encoding="utf-8")
        parts.append("## Example: Jig Data Variables (naming conventions)")
        parts.append(f"```openscad\n{data}\n```")
        parts.append("")

    parts.append(textwrap.dedent("""\
        ## Variable Naming Conventions for Jigs
        - plate = [width, depth, height];
        - studs = [[x, y, diameter], ...];       // through-holes for stud checking
        - pads = [[x, y, diameter, height], ...]; // underside contact pads
        - hook = [x_off, y_off, width, depth, height]; // registration ledge
        - handle_pos = [x, y];                   // handle knob position
        - label_lines = ["LINE1", "LINE2"];       // embossed text

        ## Output Rules
        - Always set $fn = 64; at the top
        - Always produce geometry that renders to a valid 3D solid
        - Use modules to organize complex geometry
        - Use difference() for holes, union() for combining parts
    """))

    return "\n".join(parts)


def call_ollama(
    messages: list[dict],
    model: str = "qwen2.5:14b",
    temperature: float = DEFAULT_TEMPERATURE,
    base_url: str = OLLAMA_URL,
    timeout: int = 180,
) -> str:
    """Send messages to Ollama /api/chat and return the assistant response."""
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 4096,
        },
    }

    try:
        result = _post_json(url, payload, timeout)
    except Exception as e:
        err = str(e)
        if "Connection" in err or "refused" in err or "URLError" in err:
            print(f"ERROR: Cannot reach Ollama at {base_url}")
            print("Is Ollama running? Try: ollama serve")
            sys.exit(1)
        raise

    return result["message"]["content"]


def extract_scad_code(response_text: str) -> str | None:
    """Extract OpenSCAD code from LLM response."""
    # Try fenced code block with openscad/scad tag
    m = re.search(r"```(?:openscad|scad)\s*\n(.*?)```", response_text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Fallback: any fenced code block
    m = re.search(r"```\s*\n(.*?)```", response_text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Last resort: if response looks like raw OpenSCAD
    stripped = response_text.strip()
    if re.match(r"^(//|\$fn|module|cube|difference|union|[a-z_]\w*\s*=)", stripped):
        return stripped

    return None


def validate_and_export(scad_path: Path, stl_path: Path) -> tuple[bool, str]:
    """Run OpenSCAD on the .scad file and export STL. Returns (success, stderr)."""
    cmd = [OPENSCAD_EXE, "-o", str(stl_path), str(scad_path)]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=OPENSCAD_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return False, "OpenSCAD timed out (model may be too complex)"

    stderr = result.stderr.strip()

    if result.returncode == 0:
        if stl_path.exists() and stl_path.stat().st_size > 0:
            return True, stderr
        return False, "OpenSCAD exited OK but STL is empty/missing"

    return False, stderr


def run_pipeline(
    prompt: str,
    system_prompt: str,
    model: str,
    temperature: float,
    max_retries: int,
    scad_path: Path,
    stl_path: Path,
    modify_file: Path | None = None,
) -> bool:
    """Main pipeline: prompt → LLM → extract → validate → retry."""
    # Build initial user message
    if modify_file and modify_file.exists():
        existing_code = modify_file.read_text(encoding="utf-8")
        user_content = (
            f"Here is the existing OpenSCAD code:\n"
            f"```openscad\n{existing_code}\n```\n\n"
            f"Modification requested: {prompt}\n\n"
            f"Output the complete modified code as a single ```openscad code block."
        )
    else:
        user_content = prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Attempt {attempt}/{max_retries} ---")
        print("Calling Ollama... ", end="", flush=True)

        response = call_ollama(messages, model=model, temperature=temperature)
        print("done.")

        code = extract_scad_code(response)

        if code is None:
            print("No OpenSCAD code block found in response.")
            print(f"Raw response:\n{response[:500]}")
            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your response did not contain a valid OpenSCAD code block. "
                        "Please respond with ONLY a ```openscad code block containing "
                        "the complete .scad file."
                    ),
                }
            )
            continue

        # Save the generated code
        scad_path.parent.mkdir(parents=True, exist_ok=True)
        scad_path.write_text(code, encoding="utf-8")
        print(f"Wrote: {scad_path}")

        # Validate with OpenSCAD
        print("Validating with OpenSCAD... ", end="", flush=True)
        stl_path.parent.mkdir(parents=True, exist_ok=True)
        success, error_msg = validate_and_export(scad_path, stl_path)

        if success:
            print("valid!")
            if error_msg:
                # Print warnings (non-fatal)
                warn_lines = [
                    l
                    for l in error_msg.splitlines()
                    if "WARNING" in l or "DEPRECATED" in l
                ]
                if warn_lines:
                    print(f"Warnings: {len(warn_lines)} (non-fatal)")
            print(f"\nSTL exported: {stl_path}")
            print(f"SCAD source: {scad_path}")
            return True

        print("FAILED.")
        print(f"Error:\n{error_msg[:800]}")

        if attempt < max_retries:
            # Include the source code with line numbers so the LLM can see exactly what's wrong
            numbered_code = "\n".join(
                f"{i+1}: {line}" for i, line in enumerate(code.splitlines())
            )
            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The code you generated has an error. "
                        f"OpenSCAD returned:\n{error_msg}\n\n"
                        f"Here is your code with line numbers:\n{numbered_code}\n\n"
                        f"IMPORTANT REMINDER: OpenSCAD does NOT support destructuring "
                        f"in for loops. Use for(p=array) then p[0], p[1] instead of "
                        f"for([x,y]=array). Also text() is 2D only — use "
                        f"linear_extrude(height=1.5) text(...) for 3D.\n\n"
                        f"Please fix the code and respond with the corrected "
                        f"complete ```openscad code block."
                    ),
                }
            )
        else:
            print(f"\nMax retries reached. Last code saved to: {scad_path}")

    return False


def interactive_mode(
    system_prompt: str,
    model: str,
    temperature: float,
    max_retries: int,
    scad_path: Path,
    stl_path: Path,
):
    """Interactive REPL for multi-turn OpenSCAD generation."""
    messages = [{"role": "system", "content": system_prompt}]
    turn = 0

    print("\n=== Interactive OpenSCAD Generator ===")
    print("Type your prompt. Type 'q' to quit.\n")

    while True:
        try:
            user_input = input("Prompt> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("q", "quit", "exit"):
            print("Exiting.")
            break

        if not user_input:
            continue

        turn += 1
        turn_scad = scad_path.parent / f"llm_output_{turn:03d}.scad"
        turn_stl = stl_path.parent / f"llm_output_{turn:03d}.stl"

        messages.append({"role": "user", "content": user_input})

        # Run through validation loop
        attempt_messages = list(messages)
        success = False

        for attempt in range(1, max_retries + 1):
            print(f"\n--- Turn {turn}, Attempt {attempt}/{max_retries} ---")
            print("Calling Ollama... ", end="", flush=True)

            response = call_ollama(
                attempt_messages, model=model, temperature=temperature
            )
            print("done.")

            code = extract_scad_code(response)

            if code is None:
                print("No code block found.")
                attempt_messages.append({"role": "assistant", "content": response})
                attempt_messages.append(
                    {
                        "role": "user",
                        "content": "Please respond with ONLY a ```openscad code block.",
                    }
                )
                continue

            turn_scad.write_text(code, encoding="utf-8")
            print(f"Wrote: {turn_scad}")

            print("Validating... ", end="", flush=True)
            valid, err = validate_and_export(turn_scad, turn_stl)

            if valid:
                print("valid!")
                print(f"STL: {turn_stl}")
                messages.append({"role": "assistant", "content": response})
                success = True
                break
            else:
                print(f"FAILED: {err[:300]}")
                if attempt < max_retries:
                    attempt_messages.append({"role": "assistant", "content": response})
                    attempt_messages.append(
                        {
                            "role": "user",
                            "content": f"Error: {err}\nPlease fix and resubmit.",
                        }
                    )

        if not success:
            print(f"Could not produce valid code. Last attempt: {turn_scad}")
            messages.append({"role": "assistant", "content": response})

        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OpenSCAD code using a local Ollama LLM."
    )
    parser.add_argument("prompt", nargs="?", default=None, help="Natural language prompt")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Interactive multi-turn mode"
    )
    parser.add_argument(
        "--modify", "-m", type=str, default=None,
        help="Path to existing .scad file to modify",
    )
    parser.add_argument("--model", default=None, help="Ollama model name (auto-detects if omitted)")
    parser.add_argument(
        "--list-models", action="store_true", help="List available Ollama models and exit"
    )
    parser.add_argument(
        "--retries", type=int, default=DEFAULT_MAX_RETRIES, help="Max validation retries"
    )
    parser.add_argument(
        "--temperature", type=float, default=DEFAULT_TEMPERATURE, help="LLM temperature"
    )
    parser.add_argument(
        "--output-scad", default=None, help="Output .scad path"
    )
    parser.add_argument(
        "--output-stl", default=None, help="Output .stl path"
    )
    parser.add_argument(
        "--ollama-url", default=OLLAMA_URL, help="Ollama base URL"
    )
    parser.add_argument(
        "--no-validate", action="store_true", help="Skip OpenSCAD validation"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).parent
    base_url = args.ollama_url

    # --list-models: show what's available and exit
    if args.list_models:
        models = list_available_models(base_url)
        if models:
            print("Available Ollama models:")
            for m in models:
                print(f"  {m}")
        else:
            print("No models found. Is Ollama running?")
        sys.exit(0)

    # Auto-detect model if not specified
    model = args.model or get_default_model(base_url)
    print(f"Using model: {model}")

    scad_path = Path(args.output_scad) if args.output_scad else root / "generated" / "llm_output.scad"
    stl_path = Path(args.output_stl) if args.output_stl else root / "out" / "llm_output.stl"

    # Build system prompt from templates on disk
    system_prompt = build_system_prompt(root)

    if args.interactive:
        interactive_mode(
            system_prompt, model, args.temperature,
            args.retries, scad_path, stl_path,
        )
        return

    if not args.prompt:
        print("Error: provide a prompt or use --interactive")
        print('Example: python llm_gen_scad.py "A box 50x30x10mm with a center hole"')
        sys.exit(1)

    modify_file = Path(args.modify) if args.modify else None

    if args.no_validate:
        # Just generate code, no OpenSCAD validation
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": args.prompt},
        ]
        print("Calling Ollama... ", end="", flush=True)
        response = call_ollama(messages, model=model, temperature=args.temperature)
        print("done.")
        code = extract_scad_code(response)
        if code:
            scad_path.parent.mkdir(parents=True, exist_ok=True)
            scad_path.write_text(code, encoding="utf-8")
            print(f"Wrote: {scad_path} (not validated)")
        else:
            print("No code block found in response.")
            print(f"Raw:\n{response[:500]}")
        return

    success = run_pipeline(
        prompt=args.prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=args.temperature,
        max_retries=args.retries,
        scad_path=scad_path,
        stl_path=stl_path,
        modify_file=modify_file,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
