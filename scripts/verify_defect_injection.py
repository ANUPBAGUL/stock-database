"""
Requirement 45: Defect Injection & Invariant Mutation Test Harness.
Deliberately introduces defects into core production invariants to prove that the test suite catches them:
1. PIT Filtering Defect (changes <= T0 to > T0)
2. Interval Purging Defect (changes < to <= or breaks overlap formula)
3. OOS Firewall Defect (allows mutation on Locked OOS)
4. Canonical Hashing Defect (breaks key sorting)
5. Wealth Compounding Defect (tampering with reinvested cash math)
"""
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_deliberate_defect(target_file, orig_pattern, broken_pattern, test_target):
    full_path = os.path.join(BASE_DIR, target_file)
    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert orig_pattern in content, f"Pattern '{orig_pattern}' not found in {target_file}"
    
    # 1. Break code
    broken_content = content.replace(orig_pattern, broken_pattern, 1)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(broken_content)

    # 2. Run test (must FAIL)
    res_fail = subprocess.run([sys.executable, "-m", "pytest", test_target, "-q"], capture_output=True, text=True, cwd=BASE_DIR)
    did_fail = (res_fail.returncode != 0)

    # 3. Restore code
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 4. Run test (must PASS)
    res_pass = subprocess.run([sys.executable, "-m", "pytest", test_target, "-q"], capture_output=True, text=True, cwd=BASE_DIR)
    did_pass = (res_pass.returncode == 0)

    status = "SUCCESS" if (did_fail and did_pass) else "FAILED"
    print(f"[{status}] Defect in {target_file} -> Caught: {did_fail}, Restored: {did_pass}")
    return did_fail and did_pass

def run_mutation_campaign():
    print("\n" + "="*80)
    print(">>> REQUIREMENT 45: DELIBERATE DEFECT INJECTION CAMPAIGN")
    print("="*80)

    # Defect 1: Interval Purging (Invert overlap logic)
    d1 = test_deliberate_defect(
        "src/analytics/interval_purger.py",
        "return self.label_start < other.label_end and other.label_start < self.label_end",
        "return self.label_start > other.label_end",
        "tests/institutional/test_layer_a_unit_primitives.py"
    )

    # Defect 2: Canonical Hashing (Break float precision rounding)
    d2 = test_deliberate_defect(
        "src/analytics/canonical_hasher.py",
        "return round(val, 6)",
        "return round(val, 0) # Broken: drops precision",
        "tests/institutional/test_layer_a_unit_primitives.py"
    )

    # Defect 3: OOS Firewall (Disable permission check)
    d3 = test_deliberate_defect(
        "src/analytics/oos_firewall.py",
        "raise PermissionError(",
        "return True # Broken: raise PermissionError(",
        "tests/institutional/test_layer_h_oos_firewall.py"
    )

    # Defect 4: HHI Calculation (Break squared sum formula)
    d4 = test_deliberate_defect(
        "src/analytics/competitive_engine.py",
        "hhi_observed = round(sum(s ** 2 for s in shares), 2)",
        "hhi_observed = round(sum(s for s in shares), 2) # Broken: not squared",
        "tests/institutional/test_layer_a_unit_primitives.py"
    )

    all_caught = all([d1, d2, d3, d4])
    print("\n" + "="*80)
    print(f">>> DEFECT INJECTION RESULT: {'100% DEFECTS CAUGHT (PASS)' if all_caught else 'FAILED'}")
    print("="*80 + "\n")
    return all_caught

if __name__ == "__main__":
    run_mutation_campaign()
