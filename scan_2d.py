import subprocess
import numpy as np
import re
import os
import glob

phi_values  = np.linspace(0.5, 1.3, 15)
M4_values   = np.array([1e-8, 2e-8, 3e-8, 4e-8, 4.78e-8, 6e-8, 8e-8, 1e-7])

target_w     = -0.856
target_Omega =  0.68
tolerance_w  =  0.01
tolerance_O  =  0.02

print(f"{'phi_ini':>10}  {'scf_M4':>12}  {'w_today':>10}  {'Omega_phi':>10}  {'status':>10}")
print("-" * 60)

best = []

for M4 in M4_values:
    for phi_ini in phi_values:

        with open("mytest.ini", "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if re.match(r"^\s*scf_phi_ini\s*=", line):
                new_lines.append(f"scf_phi_ini = {phi_ini:.6f}\n")
            elif re.match(r"^\s*scf_parameters\s*=", line):
                new_lines.append(f"scf_parameters = {phi_ini:.6f}, 0.0\n")
            elif re.match(r"^\s*scf_M4\s*=", line):
                new_lines.append(f"scf_M4 = {M4:.6e}\n")
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

            # Check if both constraints are satisfied
            w_ok     = abs(w_today   - target_w)     < tolerance_w
            Omega_ok = abs(Omega_phi - target_Omega) < tolerance_O

            status = ""
            if w_ok and Omega_ok:
                status = "<-- MATCH"
                best.append((phi_ini, M4, w_today, Omega_phi))

            print(f"{phi_ini:>10.4f}  {M4:>12.3e}  "
                  f"{w_today:>10.4f}  {Omega_phi:>10.4f}  {status}")

            for bf in bg_files:
                os.remove(bf)

        except Exception as e:
            print(f"{phi_ini:>10.4f}  {M4:>12.3e}  FAILED: {e}")

print("\n=== BEST MATCHES ===")
print(f"{'phi_ini':>10}  {'scf_M4':>12}  {'w_today':>10}  {'Omega_phi':>10}")
for b in best:
    print(f"{b[0]:>10.4f}  {b[1]:>12.3e}  {b[2]:>10.4f}  {b[3]:>10.4f}")

