import numpy as np

data = np.loadtxt("output/mytest66_background.dat")

# Column indices (0-based)
z         = data[:, 0]
tau       = data[:, 2]   # conformal time [Mpc]
H         = data[:, 3]   # H [1/Mpc]
w_phi     = data[:, 15]  # w_scf
rho_scf   = data[:, 13]  # rho_scf
p_scf     = data[:, 14]  # p_scf

# Method 1: dw/dN using finite differences
# N = ln(a) = -ln(1+z)
a   = 1.0 / (1.0 + z)
N   = np.log(a)

dw_dN = np.gradient(w_phi, N)

# Method 2: dw/dtau using finite differences
dw_dtau = np.gradient(w_phi, tau)

# Method 3: dw/dz using finite differences
dw_dz = np.gradient(w_phi, z)

# Today = last row (z=0)
print("=== w_phi TODAY ===")
print(f"z today         = {z[-1]:.6f}")
print(f"w_phi today     = {w_phi[-1]:.6f}")
print(f"dw/dN today     = {dw_dN[-1]:.6f}   (target: 0.53?)")
print(f"dw/dtau today   = {dw_dtau[-1]:.6e}")
print(f"dw/dz today     = {dw_dz[-1]:.6f}")

# Also print last 5 rows to see z=0 behavior
print("\n=== LAST 5 ROWS ===")
print(f"{'z':>10}  {'w_phi':>10}  {'dw/dN':>12}  {'dw/dz':>12}")
for i in range(-5, 0):
    print(f"{z[i]:>10.4f}  {w_phi[i]:>10.6f}  {dw_dN[i]:>12.6f}  {dw_dz[i]:>12.6f}")
