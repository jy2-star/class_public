from classy import Class

cosmo = Class()

cosmo.set({
'h':0.703,
'omega_b':0.0224,
'omega_cdm':0.12,
'YHe':0.245,

'Omega_scf':0.7,

'scf_M4':9.35e-8,
'scf_f':1.0,

'scf_parameters':'1.0,0.5,0.0',
'scf_tuning_index':1,

'output':''
})

cosmo.compute()

print("CLASS finished successfully")
