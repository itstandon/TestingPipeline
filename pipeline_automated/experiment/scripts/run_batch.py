import os
from .export_reqs import export_reqs
from .select_representations import run_select_representations
from .find_dependencies import run_find_dependencies
from .generate_testcases import run_generate_testcases
from .back_forth import run_back_forth

def main():
    print("\n" + "="*50)
    print("STARTING AUTOMATED BATCH RUN FOR SECTION 2.10")
    print("="*50)

    # 1. Export requirements for level 1 (splits by X.X, generating 2.10.txt)
    print("\n[Step 1] Exporting requirements...")
    export_reqs(1)
    
    selected_file = "2.10.txt"
    req_dir = "../generated_requirements"
    file_path = os.path.join(req_dir, selected_file)
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        req_text = f.read()
        
    # 2. Select representations
    print("\n[Step 2] Selecting representations via LLM...")
    run_select_representations(req_text, selected_file)
    
    # 3. Find dependencies
    print("\n[Step 3] Finding dependencies between requirements...")
    run_find_dependencies(req_text, selected_file)
    
    # 4. Generate test cases
    print("\n[Step 4] Generating test cases for selected representations...")
    run_generate_testcases(req_text, selected_file)
    
    # 5. Run back-and-forth
    print("\n[Step 5] Running back-and-forth SOTA dialogue evaluation...")
    run_back_forth(req_text, selected_file)
    
    print("\n" + "="*50)
    print("AUTOMATED BATCH RUN COMPLETED SUCCESSFULLY!")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
