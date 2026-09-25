import pandas as pd
import os


def run_coverage_analysis():
    csv_file = "results/coverage/coverage_mapping.csv"

    if not os.path.exists(csv_file):
        print(f"\nError: {csv_file} not found.")
        return

    df = pd.read_csv(csv_file)
    req_cols = [c for c in df.columns if c.startswith("R")]

    print("=" * 60)
    print("COVERAGE ANALYSIS")
    print("=" * 60)

    print("\nCoverage Per Representation")
    print("-" * 60)
    representation_results = []
    for rep in df["representation"].unique():
        subset = df[df["representation"] == rep]
        covered = (subset[req_cols].sum(axis=0) > 0).sum()
        total = len(req_cols)
        coverage = round((covered / total) * 100, 2)
        representation_results.append((rep, covered, total, coverage))

    representation_results.sort(key=lambda x: x[3], reverse=True)

    for rep, covered, total, coverage in representation_results:
        print(f"{rep:20s} {covered}/{total} ({coverage:.2f}%)")

    print("\nRequirement Coverage")
    print("-" * 60)
    for req in req_cols:
        count = df[req].sum()
        print(f"{req}: covered by {count} test cases")

    print("\nMissing Requirements")
    print("-" * 60)
    for rep in df["representation"].unique():
        subset = df[df["representation"] == rep]
        missing = [req for req in req_cols if subset[req].sum() == 0]
        print(f"\n{rep}:")
        if missing:
            print("Missing ->", ", ".join(missing))
        else:
            print("All requirements covered")

    overall_covered = (df[req_cols].sum(axis=0) > 0).sum()
    overall_total = len(req_cols)
    overall_percent = round((overall_covered / overall_total) * 100, 2)

    print("\nOverall Coverage")
    print("-" * 60)
    print(f"{overall_covered}/{overall_total} ({overall_percent:.2f}%)")

    if representation_results:
        best = representation_results[0]
        print("\nBest Representation")
        print("-" * 60)
        print(f"{best[0]} with {best[3]:.2f}% coverage")

    print("\nDone.")