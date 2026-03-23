import subprocess
import numpy as np
import re
import os
import glob

phi_values = np.linspace(0.5, 2.0, 30)

print(f"{'phi_ini':>10}  {'w_today':>10}  {'Omega_phi':>10}")
print("-" * 35)

for phi_ini in phi_values:

    with open("mytest.ini", "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if re.match(r"^\s*scf_phi_ini\s*=", line):
            new_lines.append(f"scf_phi_ini = {phi_ini:.6f}\n")
        elif re.match(r"^\s*scf_parameters\s*=", line):
            new_lines.append(f"scf_parameters = {phi_ini:.6f}, 0.0\n")
        else:
            new_lines.append(line)

    with open("mytest_scan.ini", "w") as f:
        f.writelines(new_lines)

    result = subprocess.run(
        ["grep", "-E", "scf_phi_ini|scf_parameters", "mytest_scan.ini"],
        capture_output=True, text=True
    )
    print(f"  [VERIFY] {result.stdout.strip()}")

    run = subprocess.run(
        ["./class", "mytest_scan.ini"],
        capture_output=True, text=True
    )

    try:
        bg_files = sorted(glob.glob("output/mytest_scan*_background.dat"))
        if not bg_files:
            print(f"{phi_ini:>10.4f}  NO OUTPUT FILE")
            continue

        data = np.loadtxt(bg_files[-1])
        w_today   = data[-1, 15]
        rho_scf   = data[-1, 13]
        rho_crit  = data[-1, 12]
        Omega_phi = rho_scf / rho_crit

        print(f"{phi_ini:>10.4f}  {w_today:>10.4f}  {Omega_phi:>10.4f}")

        for bf in bg_files:
            os.remove(bf)

    except Exception as e:
        print(f"{phi_ini:>10.4f}  FAILED: {e}")

print("\nTarget: w_today = -0.856, Omega_phi = 0.68")
