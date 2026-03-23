import subprocess
import numpy as np
import re
import os
import glob

# Narrow range around best match
phi_values = np.linspace(0.98, 1.05, 20)
M4_values  = np.linspace(7.0e-8, 9.0e-8, 20)

target_w     = -0.856
target_Omega =  0.688

best_score = 1e10
best_result = None

print(f"{'phi_ini':>10}  {'scf_M4':>12}  {'w_today':>10}  {'Omega_phi':>10}  {'score':>10}")
print("-" * 65)

for M4 in M4_values:
    for phi_ini in phi_values:

        with open("mytest.ini", "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if re.match(r"^\s*scf_phi_ini\s*=", line):
                new_lines.append(f"scf_phi_ini = {phi_ini:.8f}\n")
            elif re.match(r"^\s*scf_parameters\s*=", line):
                new_lines.append(f"scf_parameters = {phi_ini:.8f}, 0.0\n")
            elif re.match(r"^\s*scf_M4\s*=", line):
                new_lines.append(f"scf_M4 = {M4:.8e}\n")
            else:
                new_lines.append(line)

        with open("mytest_scan.ini", "w") as f:
            f.writelines(new_lines)

        run = subprocess.run(
            ["./class", "mytest_scan.ini"],
            capture_output=True, text=True
        )

        try:
            bg_files = sorted(glob.glob("output/mytest_scan*_background.dat"))
            if not bg_files:
                continue

            data = np.loadtxt(bg_files[-1])
            w_today   = data[-1, 15]
            rho_scf   = data[-1, 13]
            rho_crit  = data[-1, 12]
            Omega_phi = rho_scf / rho_crit

            # Combined score: distance from both targets
            score = (w_today - target_w)**2 + (Omega_phi - target_Omega)**2

            if score < best_score:
                best_score  = score
                best_result = (phi_ini, M4, w_today, Omega_phi)

            # Print only good candidates
            if abs(w_today - target_w) < 0.005 and abs(Omega_phi - target_Omega) < 0.005:
                print(f"{phi_ini:>10.6f}  {M4:>12.6e}  "
                      f"{w_today:>10.6f}  {Omega_phi:>10.6f}  {score:>10.6e}  <-- GOOD")

            for bf in bg_files:
                os.remove(bf)

        except Exception as e:
            print(f"{phi_ini:>10.4f}  {M4:>12.3e}  FAILED: {e}")

print("\n=== BEST RESULT ===")
if best_result:
    print(f"phi_ini   = {best_result[0]:.8f}")
    print(f"scf_M4    = {best_result[1]:.8e}")
    print(f"w_today   = {best_result[2]:.6f}  (target: {target_w})")
    print(f"Omega_phi = {best_result[3]:.6f}  (target: {target_Omega})")
    print(f"score     = {best_score:.6e}")
    print(f"\nAdd to mytest.ini:")
    print(f"  scf_phi_ini    = {best_result[0]:.8f}")
    print(f"  scf_M4         = {best_result[1]:.8e}")
    print(f"  scf_parameters = {best_result[0]:.8f}, 0.0")
