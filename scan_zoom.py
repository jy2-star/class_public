import subprocess
import numpy as np
import re
import os
import glob
import sys

# Very tight zoom around best result
phi_values = np.linspace(0.95, 1.15, 8)
M4_values  = np.linspace(8.5e-8, 1.15e-7, 8)
f_values   = np.linspace(1.18, 1.32, 8)

target_w     = -0.856
target_Omega =  0.688
target_dwdN  =  0.530

best_score  = 1e10
best_result = None

total = len(phi_values) * len(M4_values) * len(f_values)
count = 0

print(f"Running {total} CLASS evaluations...\n")
print(f"{'phi_ini':>10}  {'scf_M4':>12}  {'scf_f':>8}  "
      f"{'w':>10}  {'Omega':>10}  {'dw/dN':>10}  {'score':>12}")
print("-" * 80)

for f in f_values:
    for M4 in M4_values:
        for phi_ini in phi_values:

            count += 1
            print(f"  [{count}/{total}] phi={phi_ini:.3f}  M4={M4:.2e}  f={f:.3f} ...", end="\r")
            sys.stdout.flush()

            with open("mytest.ini", "r") as fin:
                lines = fin.readlines()

            new_lines = []
            for line in lines:
                if re.match(r"^\s*scf_phi_ini\s*=", line):
                    new_lines.append(f"scf_phi_ini = {phi_ini:.8f}\n")
                elif re.match(r"^\s*scf_parameters\s*=", line):
                    new_lines.append(f"scf_parameters = {phi_ini:.8f}, 0.0\n")
                elif re.match(r"^\s*scf_M4\s*=", line):
                    new_lines.append(f"scf_M4 = {M4:.8e}\n")
                elif re.match(r"^\s*scf_f\s*=", line):
                    new_lines.append(f"scf_f = {f:.8f}\n")
                else:
                    new_lines.append(line)

            with open("mytest_scan.ini", "w") as fout:
                fout.writelines(new_lines)

            run = subprocess.run(
                ["./class", "mytest_scan.ini"],
                capture_output=True, text=True
            )

            try:
                bg_files = sorted(glob.glob("output/mytest_scan*_background.dat"))
                if not bg_files:
                    continue

                data      = np.loadtxt(bg_files[-1])
                w_today   = data[-1, 15]
                rho_scf   = data[-1, 13]
                rho_crit  = data[-1, 12]
                Omega_phi = rho_scf / rho_crit

                z     = data[:, 0]
                a     = 1.0 / (1.0 + z)
                N     = np.log(a)
                w     = data[:, 15]
                dw_dN = np.gradient(w, N)[-1]

                score = (  (w_today   - target_w)**2     / target_w**2
                         + (Omega_phi - target_Omega)**2 / target_Omega**2
                         + (dw_dN     - target_dwdN)**2  / target_dwdN**2  )

                if score < best_score:
                    best_score  = score
                    best_result = (phi_ini, M4, f, w_today, Omega_phi, dw_dN)

                print(f"{phi_ini:>10.4f}  {M4:>12.3e}  {f:>8.4f}  "
                      f"{w_today:>10.4f}  {Omega_phi:>10.4f}  "
                      f"{dw_dN:>10.4f}  {score:>12.6e}")

                for bf in bg_files:
                    os.remove(bf)

            except Exception as e:
                print(f"  FAILED: {e}")

print("\n=== BEST RESULT ===")
if best_result:
    phi_ini, M4, f, w_today, Omega_phi, dw_dN = best_result
    print(f"phi_ini   = {phi_ini:.8f}  got w:     {w_today:.6f}  (target: {target_w})")
    print(f"scf_M4    = {M4:.8e}  got Omega: {Omega_phi:.6f}  (target: {target_Omega})")
    print(f"scf_f     = {f:.8f}  got dw/dN: {dw_dN:.6f}  (target: {target_dwdN})")
    print(f"score     = {best_score:.6e}")
    print(f"\n=== COPY THESE INTO mytest.ini ===")
    print(f"scf_phi_ini    = {phi_ini:.8f}")
    print(f"scf_M4         = {M4:.8e}")
    print(f"scf_f          = {f:.8f}")
    print(f"scf_parameters = {phi_ini:.8f}, 0.0")
