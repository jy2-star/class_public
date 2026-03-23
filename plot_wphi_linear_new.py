import numpy as np
import matplotlib.pyplot as plt

data = np.loadtxt("output/mytest65_background.dat")

z     = data[:,0]
w_phi = data[:,15]

# Sort so that z increases from 0 → high z
idx = np.argsort(z)
z = z[idx]
w_phi = w_phi[idx]

# Only plot late universe where thawing happens
mask = (z <= 5)

z_plot = z[mask]
w_plot = w_phi[mask]

plt.figure()
plt.plot(z_plot, w_plot)

plt.xlim(5,0)          # today on right
plt.ylim(-1.02,-0.80)  # zoom in thawing region

plt.xlabel("Redshift z")
plt.ylabel("w_phi(z)")
plt.title("Thawing Equation of State")

plt.grid()
plt.savefig("wphi_vs_z_linear_new.png",dpi=200)
