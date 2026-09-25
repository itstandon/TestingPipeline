import os
import json
import re
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Import LLM1 caller and models list
from .call_llm import call_llm, MODELS

load_dotenv()

# Configuration
MONGO_URL_OUTPUTS = os.getenv("MONGO_URL_OUTPUTS", "<mongo_url_for_outputs>")
LLM2_MODEL = os.getenv("LLM2_MODEL", "gpt-4o")
LLM2_API_KEY = os.getenv("LLM2_API_KEY") or os.getenv("OPENAI_API_KEY")

# Choose SOTA model (LLM2) rationale:
# GPT-4o / Gemini 1.5 Pro are chosen as SOTA models due to their advanced reasoning,
# formal methods analysis, massive context windows, and excellent instruction-following capabilities,
# making them perfect for multi-turn principal QA engineering evaluations.

# Define Evaluation Metrics matching metrics.md
METRICS = {
    "Representational Suitability Score (RSS)": "Concern Alignment, Abstraction Level, Occam's Razor, and LLM Feasibility of the chosen representations.",
    "Syntactic Form Validity (SFV)": "Syntactic, grammatical, and structural validity of the generated test cases in accordance with the chosen representation's standards.",
    "Functional Semantic Adequacy (FSA)": "Clause Coverage, Negative/Error Path Coverage, Oracle Assertiveness (assertion detail/determinism), and Boundary/Equivalence Partition Coverage."
}


def extract_thinking_and_answer(text):
    if not text:
        return "", ""
    think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if think_match:
        thinking = think_match.group(1).strip()
        answer = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return thinking, answer
    else:
        return "", text.strip()


def _llm2_mock_response(conversation_history):
    """Structured mock response used when no real LLM2 API key is configured,
    or when the real API call fails."""
    if conversation_history:
        last_content = conversation_history[-1]["content"].lower()
        if "comprehensive review" in last_content or "strengths" in last_content:
            return """<think>
Evaluating the subject model's responses:
- Strength: Selected representations align well with system concerns (Decision Tables for access control, Petri Nets for deadlocks).
- Strength: Traceability links are explicitly defined.
- Weakness: Gherkin scenario is simple and lacks boundary/negative conditions.
- Weakness: FSM transitions lack detailed guard conditions.
Summarizing this into a markdown table with strengths on the left and weaknesses on the right, omitting any numerical grading.
</think>
Here is the final comprehensive evaluation:

| Strengths (Left) | Weaknesses (Right) |
| :--- | :--- |
| **Excellent Concern Alignment (RSS)**: Successfully mapped state transitions to FSM and concurrency constraint properties to Petri Nets. | **BDD Negative Path Deficit (FSA)**: The Gherkin scenario outline covers basic success paths but lacks negative error coverage and exception triggers. |
| **Explicit Traceability Linkage**: Included clear, unambiguous linkages back to parent requirement clauses. | **FSM Transition Guard Details**: State transition definitions lack concrete conditional guard assertions. |
"""
        else:
            return ("Justify ur choices against the following framework metrics:\n"
                    "1. Representational Suitability Score (RSS): Concern Alignment, Abstraction Level, Occam's Razor, and LLM Feasibility.\n"
                    "2. Syntactic Form Validity (SFV): Adherence of test cases to the chosen representation's syntax rules and schema standards.\n"
                    "3. Functional Semantic Adequacy (FSA): Clause Coverage, Negative/Error Path Coverage, Oracle Assertiveness, and Boundary/Equivalence Coverage.\n\n"
                    "IMPORTANT: First, write your step-by-step thinking process wrapped inside <think>...</think> tags, and then write your final response.")
    else:
        return "Initial state."


def call_llm2(conversation_history, system_prompt):
    """
    Calls the SOTA Evaluator (LLM2) using the OpenAI client.
    Falls back to a structured mock response if OpenAI connection is not established.
    """
    if not LLM2_API_KEY or LLM2_API_KEY == "your_sota_api_key_here":
        return _llm2_mock_response(conversation_history)

    try:
        import openai
        client = openai.OpenAI(api_key=LLM2_API_KEY)
        messages = [{"role": "system", "content": system_prompt}] + conversation_history
        response = client.chat.completions.create(
            model=LLM2_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling LLM2 API: {e}. Falling back to mock response.")
        return _llm2_mock_response(conversation_history)


def run_back_forth(req_text, req_filename):
    print("\n" + "=" * 60)
    print("STARTING BACK-AND-FORTH DIALOGUE EVALUATION")
    print("=" * 60)

    req_name = os.path.splitext(req_filename)[0]

    # Load Representation catalog and initial prompt template
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
    catalog_path = os.path.join(_PROJECT_ROOT, "prompts", "Representations.md")
    prompt_path = os.path.join(_PROJECT_ROOT, "prompts", "select_representations.txt")

    catalog_text = ""
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog_text = f.read()
    else:
        print(f"  Warning: representations catalog not found at {catalog_path}")

    prompt_template = ""
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    else:
        print(f"  Warning: prompt template not found at {prompt_path}")

    # Define LLM2 System Persona & Instructions
    llm2_system_prompt = (
        "You are a SOTA Principal Software QA Engineer and Formal Verification Specialist acting as an Evaluator. "
        "Your goal is to conduct a multi-turn interview with a Subject LLM (LLM1) to evaluate how effectively it maps "
        "natural language requirements to appropriate test case representations and generates syntactically and semantically complete test suites. "
        "You must judge its responses against these defined framework metrics:\n"
        f"{json.dumps(METRICS, indent=2)}\n\n"
        "At each turn, evaluate the quality of LLM1's response. Be critical and professional. "
        "Guide LLM1 through the following questions, incorporating your critiques of its previous answers:\n"
        "1. Turn 1 (Initial Prompt): Let LLM1 respond to the initial mapping task based on the provided representations.\n"
        "2. Turn 2 (Metrics Justification): Ask LLM1 to justify its output against the metrics:\n"
        "   Justify ur choices against the following framework metrics:\n"
        "   1. Representational Suitability Score (RSS): Concern Alignment, Abstraction Level, Occam's Razor, and LLM Feasibility.\n"
        "   2. Syntactic Form Validity (SFV): Adherence of test cases to the chosen representation's syntax rules and schema standards.\n"
        "   3. Functional Semantic Adequacy (FSA): Clause Coverage, Negative/Error Path Coverage, Oracle Assertiveness, and Boundary/Equivalence Coverage.\n\n"
        "   IMPORTANT: Instruct LLM1 that it MUST first write its step-by-step thinking process wrapped inside <think>...</think> tags, and then write its final response."
    )

    for model in MODELS:
        print(f"\nRunning back-and-forth session for subject model (LLM1): {model}")

        # Load dependencies from previous find_dependencies execution
        model_name = model.replace(":", "_").replace("/", "_")
        dep_path = os.path.join("results/dependencies", f"{model_name}_{req_name}.json")
        deps_content = "No dependencies available."

        if os.path.exists(dep_path):
            try:
                with open(dep_path) as f:
                    deps_data = json.load(f)
                    deps_content = json.dumps(deps_data, indent=2)
            except Exception as e:
                print(f"  Warning: Could not parse dependency file: {e}")

        # Substitute prompt template for Turn 1 (Round 0)
        initial_prompt = prompt_template
        initial_prompt = initial_prompt.replace("{REQ}", req_text)
        initial_prompt = initial_prompt.replace("{DEPS}", deps_content)
        initial_prompt = initial_prompt.replace("{REPRESENTATIONS_CATALOG}", catalog_text)

        session_history = []
        llm2_chat_history = []

        # ==========================================
        # ROUND 0 (Turn 1): Initial Prompt and Response
        # ==========================================
        print("  Sending Round 0 (Turn 1 Prompt) to LLM1...")
        llm1_response_1_raw = call_llm(initial_prompt, model)
        llm1_thinking_1, llm1_answer_1 = extract_thinking_and_answer(llm1_response_1_raw)
        print("  LLM1 Round 0 response received.")

        session_history.append({
            "round": 0,
            "llm2_prompt": initial_prompt,
            "llm1_thinking": llm1_thinking_1,
            "llm1_answer": llm1_answer_1
        })

        # Pass only clean final answer to LLM2's history
        llm2_chat_history.append({"role": "user", "content": f"Here is the initial response from LLM1:\n{llm1_answer_1}"})

        # ==========================================
        # ROUND 1 (Turn 2): Metrics Justification
        # ==========================================
        print("  Generating Round 1 prompt via LLM2...")
        llm2_prompt_2 = call_llm2(llm2_chat_history, llm2_system_prompt)
        print(f"  LLM2 Round 1 Prompt:\n{llm2_prompt_2[:150]}...")

        print("  Sending Round 1 to LLM1...")
        llm1_response_2_raw = call_llm(llm2_prompt_2, model)
        llm1_thinking_2, llm1_answer_2 = extract_thinking_and_answer(llm1_response_2_raw)
        print("  LLM1 Round 1 response received.")

        session_history.append({
            "round": 1,
            "llm2_prompt": llm2_prompt_2,
            "llm1_thinking": llm1_thinking_2,
            "llm1_answer": llm1_answer_2
        })

        llm2_chat_history.append({"role": "assistant", "content": llm2_prompt_2})
        llm2_chat_history.append({"role": "user", "content": f"LLM1's response to metrics justification:\n{llm1_answer_2}"})

        # ==========================================
        # ROUND 2 (Turn 3): Final Evaluation
        # ==========================================
        print("  Generating final session review table via LLM2...")
        llm2_review_prompt = (
            "Provide a final comprehensive review of LLM1's answers based on the SOTA metrics. "
            "Wrap your internal reasoning/thinking process in <think>...</think> tags, "
            "followed by your final output, which MUST be a markdown table detailing strengths "
            "(left column) and weaknesses (right column) of LLM1's performance, without any numerical grading or scores."
        )
        llm2_chat_history.append({"role": "user", "content": llm2_review_prompt})

        final_review_raw = call_llm2(llm2_chat_history, llm2_system_prompt)
        llm2_thinking_3, llm2_answer_3 = extract_thinking_and_answer(final_review_raw)
        print("  Session review complete.")

        session_history.append({
            "round": 2,
            "llm2_thinking": llm2_thinking_3,
            "llm2_answer": llm2_answer_3
        })

        # Save results in JSON structure
        session_document = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "requirement_file": req_filename,
            "llm1_model": model,
            "llm2_model": LLM2_MODEL,
            "metrics": METRICS,
            "conversation": session_history,
            "llm2_final_evaluation": llm2_answer_3
        }

        # Save to local results directory
        local_out_dir = "results/back_forth"
        os.makedirs(local_out_dir, exist_ok=True)
        local_out_path = os.path.join(local_out_dir, f"{model_name}_{req_name}.json")
        with open(local_out_path, "w", encoding="utf-8") as f:
            json.dump(session_document, f, indent=2)
        print(f"  Saved session transcript locally to {local_out_path}")

        # Store to MongoDB
        store_to_mongodb(session_document)

    print("\nAll back-and-forth sessions completed.")


def store_to_mongodb(document):
    """
    Attempts to connect and save the document to MongoDB.
    Safely bypasses connection if the URI is a placeholder.
    """
    if not MONGO_URL_OUTPUTS or MONGO_URL_OUTPUTS.startswith("<") or "oputputs" in MONGO_URL_OUTPUTS:
        print("  [INFO] MongoDB output database URL is currently set to placeholder. Skipping Mongo storage.")
        return

    try:
        print("  Connecting to MongoDB outputs collection...")
        client = MongoClient(MONGO_URL_OUTPUTS, serverSelectionTimeoutMS=5000)
        db = client["back_forth_evaluation"]
        collection = db["sessions"]

        result = collection.insert_one(document)
        print(f"  Successfully saved transcript to MongoDB (Inserted ID: {result.inserted_id})")
    except Exception as e:
        print(f"  [ERROR] Failed to save to MongoDB: {e}")