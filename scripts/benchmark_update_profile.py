import timeit
import sys
import os

# Add the scripts directory to sys.path so we can import replace_latest_repo_section
sys.path.append(os.path.join(os.getcwd(), 'scripts'))

from update_profile_activity import START_MARKER, END_MARKER, replace_latest_repo_section as optimized_implementation

# Ensure START_MARKER and END_MARKER are near the end of a large string
BASE_TEXT = "This is some filler text.\n" * 10
SAMPLE_README = f"{BASE_TEXT}{START_MARKER}\n- [Old Repo](https://github.com/old/repo)\n{END_MARKER}\n{BASE_TEXT}"

NEW_REPO_LINES = [
    "- [New Repo 1](https://github.com/new/repo1) - New description 1 <sub>2024-01-01</sub>",
    "- [New Repo 2](https://github.com/new/repo2) - New description 2 <sub>2024-01-01</sub>",
]

def current_implementation(readme_text, repo_lines):
    start_index = readme_text.find(START_MARKER)
    end_index = readme_text.find(END_MARKER)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise ValueError("Required README markers are missing or out of order.")
    section_body = "\n".join(repo_lines) if repo_lines else "- No recent repos right now."
    replacement = f"{START_MARKER}\n{section_body}\n{END_MARKER}"
    current = readme_text[start_index : end_index + len(END_MARKER)]
    return readme_text.replace(current, replacement, 1)

def optimized_implementation(readme_text, repo_lines):
    start_index = readme_text.find(START_MARKER)
    end_index = readme_text.find(END_MARKER)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        raise ValueError("Required README markers are missing or out of order.")
    section_body = "\n".join(repo_lines) if repo_lines else "- No recent repos right now."
    replacement = f"{START_MARKER}\n{section_body}\n{END_MARKER}"
    return f"{readme_text[:start_index]}{replacement}{readme_text[end_index + len(END_MARKER):]}"

def run_benchmark():
    iterations = 1000000

    current_time = timeit.timeit(lambda: current_implementation(SAMPLE_README, NEW_REPO_LINES), number=iterations)
    optimized_time = timeit.timeit(lambda: optimized_implementation(SAMPLE_README, NEW_REPO_LINES), number=iterations)

    print(f"Benchmark results over {iterations} iterations:")
    print(f"Current implementation:   {current_time:.6f} seconds")
    print(f"Optimized implementation: {optimized_time:.6f} seconds")

    improvement = (current_time - optimized_time) / current_time * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    run_benchmark()
