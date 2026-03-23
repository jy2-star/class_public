import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from classy import Class

cosmo = Class()

cosmo.set({
'h':0.703,
'omega_b':0.0224,
'omega_cdm':0.119,
'YHe':0.245,

'Omega_scf':0.7,

'scf_M4':9.35e-8,
'scf_f':1.0,

'scf_parameters':'1.0,0.5,0.0',
'scf_tuning_index':1,

'recombination':'recfast',
'output':''
})

cosmo.compute()

# get background evolution
bg = cosmo.get_background()
print(bg.keys())
z = bg['z']

# density parameters
Omega_r = bg['Omega_r(z)']
Omega_m = bg['Omega_m(z)']
Omega_phi = bg['(.)rho_scf'] / bg['(.)rho_crit']

# equation of state
w_phi = bg['(.)w_scf']

# ---------- Plot densities ----------
plt.figure()

plt.semilogx(z, Omega_r, label='Radiation')
plt.semilogx(z, Omega_m, label='Matter')
plt.semilogx(z, Omega_phi, label='Scalar Field')

plt.gca().invert_xaxis()

plt.xlabel("z")
plt.ylabel("Omega_i(z)")
plt.legend()
plt.title("Cosmic Energy Budget")

plt.savefig("Omega_evolution.png")
plt.close()

# ---------- Plot equation of state ----------
plt.figure()

plt.semilogx(z, w_phi)

plt.gca().invert_xaxis()

plt.xlabel("z")
plt.ylabel("w_phi(z)")
plt.title("Scalar Field Equation of State")

plt.savefig("w_phi_evolution.png")
plt.close()

cosmo.struct_cleanup()
cosmo.empty()

print("Plots saved: Omega_evolution.png and w_phi_evolution.png")
