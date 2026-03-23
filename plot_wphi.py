import numpy as np
import matplotlib.pyplot as plt

# Load background file
data = np.loadtxt("output/mytest63_background.dat")

# Column definitions from CLASS header:
# 1:z
# 16:w_scf

z     = data[:,0]
w_phi = data[:,15]

# Sort in increasing z (important for plotting)
idx = np.argsort(z)
z = z[idx]
w_phi = w_phi[idx]

print("w_today =", w_phi[-1])
print("min w   =", np.min(w_phi))
print("max w   =", np.max(w_phi))

plt.figure()

plt.plot(z, w_phi)

plt.xscale('log')
plt.xlim(1e4, 0.01)        # show late-time thawing clearly
plt.ylim(-1.02, -0.80)

plt.xlabel("Redshift z")
plt.ylabel("w_phi(z)")
plt.title("Thawing Quintessence")

plt.grid()
plt.savefig("wphi_vs_z_mytest63.png", dpi=200)

print("Saved as wphi_vs_z_mytest63.png")
