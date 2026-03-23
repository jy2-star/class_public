import numpy as np
import matplotlib.pyplot as plt
import subprocess
import os

# -------- SETTINGS --------
chain_file = "../montepython_public/chains/bao_phi_M4_wide_long/2026-03-20_30000__1.txt"
n_samples = 10

# -------- LOAD CHAIN --------
data = np.loadtxt(chain_file)

phi_ini = data[:,2]
M4 = data[:,3]

np.random.seed(0)
indices = np.random.choice(len(phi_ini), n_samples, replace=False)

all_z = []
all_w = []

for i, idx in enumerate(indices):

    phi = phi_ini[idx]
    m4  = M4[idx]

    print(f"Running sample {i}: phi={phi}, M4={m4}")

    ini_name = f"temp_{i}.ini"
    root_name = f"temp_{i}"

    with open(ini_name, "w") as f:
        f.write(f"""
h = 0.703
omega_b = 0.02249
omega_cdm = 0.1120

Omega_Lambda = 0
Omega_fld = 0

scf_M4 = {m4}
scf_f  = 1.18

scf_phi_ini = {phi}
scf_phi_prime_ini = 0.0

scf_parameters = {phi},0.0
scf_tuning_index = -1

output = mPk
write background = yes
root = output/{root_name}_
""")

    # -------- RUN CLASS --------
    subprocess.run(["./class", ini_name])

    # -------- LOAD OUTPUT --------
    output_file = None

    for file in os.listdir("output"):
        if "background.dat" in file and f"temp_{i}" in file:
            output_file = os.path.join("output", file)
            break

    if output_file is None:
        print(f"⚠️ Missing output for temp_{i}")
        continue

    bg = np.loadtxt(output_file)

    z = bg[:,0]
    w = bg[:,15]

    idx_sort = np.argsort(z)
    z = z[idx_sort]
    w = w[idx_sort]

    all_z.append(z)
    all_w.append(w)

# -------- PLOT --------
plt.figure()

for z, w in zip(all_z, all_w):
    plt.plot(z, w, alpha=0.5)

plt.xscale('log')
plt.xlabel('z')
plt.ylabel('w_phi(z)')
plt.title('w(z) from MCMC samples (eBOSS)')
plt.grid()

plt.savefig("w_band.png", dpi=300)
plt.close()

print("✅ Saved: w_band.png")
