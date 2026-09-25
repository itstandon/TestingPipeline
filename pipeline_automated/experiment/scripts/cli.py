import os
from .export_reqs import export_reqs
from .find_dependencies import run_find_dependencies
from .generate_testcases import run_generate_testcases
from .compare_with_expert import run_compare_with_expert
from .coverage_analysis import run_coverage_analysis
from .back_forth import run_back_forth
from .run_metrics import run_evaluate_metrics

from dotenv import load_dotenv
load_dotenv()


def post_generation_menu():
    while True:
        print("\n" + "=" * 50)
        print("What would you like to do next?")
        print("=" * 50)
        print("1 -> Back and forth")
        print("2 -> Compare representations with expert")
        print("3 -> Coverage analysis")
        print("4 -> Evaluate metrics (Gate 2 SFV)")
        print("q -> Quit menu")

        choice = input("\nChoice: ").strip().lower()

        if choice == "1":
            run_back_forth(req_text, selected_file)
        elif choice == "2":
            run_compare_with_expert(req_text, selected_file)
        elif choice == "3":
            run_coverage_analysis()
        elif choice == "4":
            run_evaluate_metrics(req_text, selected_file)
        elif choice == "q":
            break
        else:
            print("Please enter 1, 2, 3, or q.")


def print_hpc_guide():
    print("\n" + "=" * 60)
    print("                HPC DEPLOYMENT & EXECUTION GUIDE")
    print("=" * 60)
    print("Steps to execute this pipeline on the IIIT-H Ada HPC:")
    print("\n1. SSH into the login node:")
    print("   $ ssh arushi.tandon@ada.iiit.ac.in")
    print("   Password: B99Win1$")
    print("\n2. Allocate an interactive GPU node (e.g., 10 cores, 1 GPU):")
    print("   $ sinteractive -c 10 -A research -g 1")
    print("\n3. SSH into the allocated GPU node (check the node assigned, e.g., gnode025):")
    print("   $ ssh gnode025")
    print("\n4. Navigate to the pipeline directory and activate the environment:")
    print("   $ cd ~/pipeline")
    print("   $ source venv/bin/activate")
    print("\n5. Start the local Ollama server in the background:")
    print("   $ export LD_LIBRARY_PATH=~/.local/ollama/lib:$LD_LIBRARY_PATH")
    print("   $ ~/.local/bin/ollama serve > ~/ollama_serve.log 2>&1 &")
    print("\n6. Verify Ollama is running and responsive:")
    print("   $ curl -s http://localhost:11434")
    print("\n7. Run the pipeline CLI:")
    print("   $ cd ~/pipeline/pipeline_automated/experiment")
    print("   $ python3 scripts/cli.py")
    print("\n8. After completion, clean up running processes and exit:")
    print("   $ pkill ollama")
    print("   $ deactivate")
    print("   $ exit")
    print("=" * 60 + "\n")


def main():

    print("=" * 50)
    print("Requirement Export & Select Utility")
    print("=" * 50)


    while True:
        print("\nChoose grouping level:\n")

        print("0 -> X")
        print("1 -> X.X")
        print("2 -> X.X.X")
        print("3 -> X.X.X.X")
        print("h -> HPC Deployment Guide")

        while True:
            try:
                inp = input("\nGrouping level / Option: ").strip().lower()
                if inp == "q":
                    print("Exiting.")
                    return
                elif inp == "h":
                    print_hpc_guide()
                    print("\nChoose grouping level:\n")
                    print("0 -> X")
                    print("1 -> X.X")
                    print("2 -> X.X.X")
                    print("3 -> X.X.X.X")
                    print("h -> HPC Deployment Guide")
                    continue
                level = int(inp)
                if level < 0:
                    raise ValueError
                break
            except ValueError:
                print("Please enter a level (0-3), 'h' for HPC guide, or 'q' to quit.")

        export_reqs(level)

        # List generated requirements
        req_dir = "../generated_requirements"
        if not os.path.exists(req_dir):
            print(f"Error: Directory {req_dir} not found.")
            continue

        files = sorted([f for f in os.listdir(req_dir) if os.path.isfile(os.path.join(req_dir, f))])

        if not files:
            print(f"No files found in {req_dir}.")
            continue

        print("\nGenerated requirement files:")
        for i, f in enumerate(files):
            print(f"{i + 1} -> {f}")

        while True:
            try:
                choice = int(input("\nSelect a file by number: "))
                if 1 <= choice <= len(files):
                    selected_file = files[choice - 1]
                    break
                else:
                    print(f"Please enter a number between 1 and {len(files)}.")
            except ValueError:
                print("Please enter a valid integer.")

        file_path = os.path.join(req_dir, selected_file)
        print(f"\nReading {file_path}...")

        with open(file_path, "r", encoding="utf-8") as f:
            req_text = f.read()

        print("\nFinding dependencies between requirements...")
        run_find_dependencies(req_text, selected_file)
        print("Dependency analysis complete.")

        # Step 1 (was: select representations, then generate) -- now a
        # single step: generate test cases directly from reqs + deps,
        # in both the basic prompt and the metrics-aware prompt.
        #   phase1_basic:          {REQ} + {DEPS} only
        #   phase2_metrics_aware:  {REQ} + {DEPS} + FSA/expert rubric
        print("\nGenerating test cases directly from requirements + dependencies "
              "(phase1_basic, phase2_metrics_aware)...")
        run_generate_testcases(req_text, selected_file)
        print("\nAll test cases generated in results/test_cases/")

        # Step 2: score every generated suite against Gate 2 (SFV) --
        # rewritten to check the fixed test-case template rather than a
        # representation's syntax. No Gate 1 (RSS) or Gate 3 (FSA) any
        # more, since there's no representation choice to validate and
        # FSA isn't part of this pipeline's automated metrics.
        print("\nEvaluating generated test cases against SFV (template conformance)...")
        run_evaluate_metrics(req_text, selected_file)
        print("\nMetrics written to results/metrics/")

        # Step 3: compare both phases against expert ground truth, where
        # it exists for this requirement file.
        print("\nComparing against expert ground truth (where available)...")
        run_compare_with_expert(req_text, selected_file)

        post_generation_menu()


if __name__ == "__main__":
    main()