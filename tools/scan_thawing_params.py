#!/usr/bin/env python3
"""
Scan scf_phi_ini, scf_f, and scf_M4 to find DESI-like thawing parameters where:
- w_scf(z=0) > -0.9 (slow thawing, not ultra-light)
- Omega_scf(z=0) ≈ 0.69 (target dark energy density)
- V''(phi_today) / H0^2 ~ O(1) (true thawing mass scale)

Effective thawing mass: m_eff^2 ~ M^4 / f^2

Usage:
  python3 tools/scan_thawing_params.py --ini mytest.ini --class ./class \
    --phi-min 0.3 --phi-max 1.2 --phi-steps 8 \
    --f-min 0.5 --f-max 2.5 --f-steps 6 \
    --m4-factor-min 0.1 --m4-factor-max 3.0 --m4-steps 8
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from itertools import product
from math import pi, cos

def read_ini_value(path, key):
    pat = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*([0-9eE+\-\.]+)")
    with open(path) as f:
        for line in f:
            m = pat.search(line)
            if m:
                return float(m.group(1))
    return None

def write_ini_with_value(src, dst, key, value):
    pat = re.compile(r"^(\s*" + re.escape(key) + r"\s*=).*$")
    replaced = False
    with open(src) as f_in, open(dst, "w") as f_out:
        for line in f_in:
            if pat.search(line):
                f_out.write(pat.sub(r"\1 %g", line) % value)
                replaced = True
            else:
                f_out.write(line)
    if not replaced:
        with open(dst, "a") as f_out:
            f_out.write("\n%s = %g\n" % (key, value))

def write_ini_with_string(src, dst, key, value):
    pat = re.compile(r"^(\s*" + re.escape(key) + r"\s*=).*$")
    replaced = False
    with open(src) as f_in, open(dst, "w") as f_out:
        for line in f_in:
            if pat.search(line):
                f_out.write(pat.sub(r"\1 %s", line) % value)
                replaced = True
            else:
                f_out.write(line)
    if not replaced:
        with open(dst, "a") as f_out:
            f_out.write("\n%s = %s\n" % (key, value))

def run_class(class_bin, ini_path, timeout=120):
    repo_root = os.path.dirname(os.path.abspath(class_bin)) or '.'
    try:
        subprocess.run(
            [class_bin, ini_path],
            cwd=repo_root,
            check=True,
            timeout=timeout,
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except subprocess.TimeoutExpired:
        return False

def find_latest_background_file():
    files = glob.glob("*_background.dat")
    if not files:
        files = glob.glob(os.path.join("output", "*_background.dat"))
    if not files:
        return None
    files.sort(key=os.path.getmtime)
    return files[-1]

def parse_background_for_thawing_analysis(path, M4, f, H0):
    """
    Return (w_scf, omega_scf, V_today, dV_today, ddV_today, phi_today) at z ≈ 0.
    Also compute thawing diagnostic: V''(phi_today) / H0^2.
    """
    with open(path) as f_file:
        lines = f_file.readlines()

    header = None
    header_idx = None
    for i in range(min(50, len(lines))):
        line = lines[i].strip()
        if not line:
            continue
        if line.startswith('#'):
            txt = line.lstrip('#').strip()
        elif line.startswith('"'):
            txt = line.lstrip('"').strip()
        else:
            txt = line
        tokens = txt.split()
        # Look for required columns
        has_rho_scf = any('rho_scf' in t for t in tokens)
        has_rho_crit = any('rho_crit' in t for t in tokens)
        has_z = any(t == 'z' or '(z)' in t or t == '(.)z' for t in tokens)
        has_w_scf = any('w_scf' in t for t in tokens)
        has_V = any('V_scf' in t for t in tokens)
        has_dV = any('dV_scf' in t for t in tokens)
        
        if has_rho_scf and has_rho_crit and has_z:
            header = tokens
            header_idx = i
            break

    if header is None:
        raise RuntimeError('Could not find header with required columns')

    def find_index(patterns):
        """Find first column matching any pattern (exact or substring)."""
        for pattern in patterns:
            if pattern in header:
                return header.index(pattern)
        for pattern in patterns:
            for j, t in enumerate(header):
                if pattern in t:
                    return j
        raise RuntimeError('Could not find column matching patterns: %s' % patterns)

    i_rho_scf = find_index(['(.)rho_scf', 'rho_scf'])
    i_rho_crit = find_index(['(.)rho_crit', 'rho_crit'])
    i_z = find_index(['(.)z', '(z)', 'z'])
    i_w_scf = find_index(['(.)w_scf', 'w_scf']) if any('w_scf' in t for t in header) else None
    i_V = find_index(['(.)V_scf', 'V_scf']) if any('V_scf' in t for t in header) else None
    i_dV = find_index(['(.)dV_scf', 'dV_scf']) if any('dV_scf' in t for t in header) else None
    i_ddV = find_index(['(.)ddV_scf', 'ddV_scf']) if any('ddV_scf' in t for t in header) else None
    i_phi = find_index(['(.)phi_scf', 'phi_scf']) if any('phi_scf' in t for t in header) else None

    data_lines = [ln for ln in lines[header_idx+1:] if ln.strip() and not ln.strip().startswith('#')]
    if not data_lines:
        raise RuntimeError('No data rows found')

    best_row = None
    best_z_diff = None
    for ln in data_lines:
        parts = ln.split()
        max_idx = max(i_rho_scf, i_rho_crit, i_z)
        if i_w_scf is not None:
            max_idx = max(max_idx, i_w_scf)
        if len(parts) <= max_idx:
            continue
        try:
            zval = float(parts[i_z])
            rho_scf = float(parts[i_rho_scf])
            rho_crit = float(parts[i_rho_crit])
            omega_scf = rho_scf / rho_crit
            
            # Parse optional columns
            w_scf = float(parts[i_w_scf]) if i_w_scf is not None and i_w_scf < len(parts) else None
            V_val = float(parts[i_V]) if i_V is not None and i_V < len(parts) else None
            dV_val = float(parts[i_dV]) if i_dV is not None and i_dV < len(parts) else None
            ddV_val = float(parts[i_ddV]) if i_ddV is not None and i_ddV < len(parts) else None
            phi_val = float(parts[i_phi]) if i_phi is not None and i_phi < len(parts) else None
        except Exception:
            continue
        
        diff = abs(zval - 0.0)
        if best_z_diff is None or diff < best_z_diff:
            best_z_diff = diff
            best_row = (w_scf, omega_scf, V_val, dV_val, ddV_val, phi_val, zval)

    if best_row is None:
        raise RuntimeError('Could not find valid row')

    w_scf, omega_scf, V_val, dV_val, ddV_val, phi_val, z_val = best_row
    
    # Fallback: compute w from rho/p if not in file
    if w_scf is None and rho_scf > 0:
        # p = phi'^2/(2a^2) - V, so w = p/rho
        # Since we don't have p directly, we use V/rho as estimate
        w_scf = -1.0 + (2.0/3.0) * (V_val / rho_scf) if V_val is not None and V_val > 0 else -1.0
    
    # Diagnostic: V''(phi_today) / H0^2
    # For V(phi) = M^4 cos^2(phi/f), V'' = M^4/f^2 * [4 cos(2*phi/f) - 2]
    # At minimum (phi=0): V''_0 = 2*M^4/f^2
    # General: V''(phi) ~ M^4/f^2 (order of magnitude)
    H0_sq = H0 * H0
    m_eff_sq = (M4 / (f * f)) if f > 0 else 0  # effective mass squared: M^4/f^2
    mass_ratio = m_eff_sq / H0_sq if H0_sq > 0 else float('inf')
    
    return w_scf, omega_scf, phi_val, ddV_val, mass_ratio, z_val

def compute_score(w_scf, omega_scf, mass_ratio, target_w=-0.85, target_omega=0.69):
    """
    Rank by: (1) w > -0.9 (true thawing), (2) Omega ≈ 0.69, (3) mass ratio ~ O(1).
    Lower score is better.
    """
    w_weight = 1.0
    omega_weight = 1.0
    mass_weight = 0.5
    
    # Penalty for being too damped (w < -0.95)
    if w_scf < -0.95:
        w_penalty = 10.0 * (-0.95 - w_scf)  # Heavy penalty for ultra-light regime
    elif w_scf < target_w:
        w_penalty = (target_w - w_scf)**2
    else:
        w_penalty = 0.2 * (w_scf - target_w)**2  # Lower penalty if less negative than target
    
    omega_penalty = (omega_scf - target_omega)**2
    
    # Prefer mass_ratio ~ O(1); penalize if too small (Hubble-dominated) or huge (classical)
    mass_penalty = (mass_ratio - 1.0)**2
    
    score = w_weight * w_penalty + omega_weight * omega_penalty + mass_weight * mass_penalty
    return score

def main():
    ap = argparse.ArgumentParser(description='Scan thawing parameters for DESI-like regime.')
    ap.add_argument('--ini', default='mytest.ini')
    ap.add_argument('--class', dest='class_bin', default='./class')
    ap.add_argument('--target-w', type=float, default=-0.85, help='Target w_scf')
    ap.add_argument('--target-omega', type=float, default=0.69, help='Target Omega_scf')
    
    ap.add_argument('--phi-min', type=float, default=0.3)
    ap.add_argument('--phi-max', type=float, default=1.2)
    ap.add_argument('--phi-steps', type=int, default=5)
    
    ap.add_argument('--f-min', type=float, default=0.5)
    ap.add_argument('--f-max', type=float, default=2.5)
    ap.add_argument('--f-steps', type=int, default=4)
    
    ap.add_argument('--m4-factor-min', type=float, default=0.5)
    ap.add_argument('--m4-factor-max', type=float, default=2.0)
    ap.add_argument('--m4-steps', type=int, default=4)
    
    args = ap.parse_args()

    # Read current M4 value and H0
    m4_orig = read_ini_value(args.ini, 'scf_M4')
    f_orig = read_ini_value(args.ini, 'scf_f')
    H0 = read_ini_value(args.ini, 'H0')
    
    if m4_orig is None:
        print('Error: scf_M4 not found in %s' % args.ini)
        sys.exit(1)
    if f_orig is None:
        print('Error: scf_f not found in %s' % args.ini)
        sys.exit(1)
    if H0 is None:
        print('Error: H0 not found in %s' % args.ini)
        sys.exit(1)

    # Generate parameter grids
    phi_values = [args.phi_min + (args.phi_max - args.phi_min) * i / max(1, args.phi_steps - 1) 
                  for i in range(args.phi_steps)]
    f_values = [args.f_min + (args.f_max - args.f_min) * i / max(1, args.f_steps - 1)
                for i in range(args.f_steps)]
    m4_factors = [args.m4_factor_min + (args.m4_factor_max - args.m4_factor_min) * i / max(1, args.m4_steps - 1)
                  for i in range(args.m4_steps)]

    results = []

    total_combos = len(phi_values) * len(f_values) * len(m4_factors)
    print('Scanning %d phi × %d f × %d M4 = %d combinations...' % 
          (len(phi_values), len(f_values), len(m4_factors), total_combos))
    print('Target: w_scf > -0.9 (thawing), Omega_scf ≈ %.2f, V\'\'(phi)/H0^2 ~ O(1)' % args.target_omega)
    print()
    print('  phi_ini      f         M4_factor      w_scf      Omega_scf   V\'\'/H0^2    Score')
    print('─' * 90)

    combo_count = 0
    for phi, f_val, m4_factor in product(phi_values, f_values, m4_factors):
        combo_count += 1
        m4 = m4_orig * m4_factor
        
        # Create temp ini with these parameters
        tmp_ini = tempfile.NamedTemporaryFile(delete=False, suffix='.ini')
        tmp_ini.close()
        
        shutil.copyfile(args.ini, tmp_ini.name)
        
        # Override all three parameters
        for key, val in [('scf_phi_ini', phi), ('scf_f', f_val), ('scf_M4', m4)]:
            tmp = tmp_ini.name + '.tmp'
            write_ini_with_value(tmp_ini.name, tmp, key, val)
            os.replace(tmp, tmp_ini.name)
        
        # Set output root to safe location
        tmp = tmp_ini.name + '.tmp'
        write_ini_with_string(tmp_ini.name, tmp, 'root', 'output/scan_')
        os.replace(tmp, tmp_ini.name)
        
        # Run CLASS
        ok = run_class(args.class_bin, tmp_ini.name)
        if not ok:
            os.unlink(tmp_ini.name)
            print('  % 8.4f   % 8.4f   % 8.4f      FAILED' % (phi, f_val, m4_factor))
            continue
        
        # Parse output
        try:
            bg = find_latest_background_file()
            if bg is None:
                print('  % 8.4f   % 8.4f   % 8.4f      NO OUTPUT' % (phi, f_val, m4_factor))
                os.unlink(tmp_ini.name)
                continue
            
            w_scf, omega_scf, phi_today, ddV_today, mass_ratio, z_val = parse_background_for_thawing_analysis(
                bg, m4, f_val, H0)
            
            # Compute score
            score = compute_score(w_scf, omega_scf, mass_ratio, args.target_w, args.target_omega)
            
            results.append((phi, f_val, m4_factor, w_scf, omega_scf, mass_ratio, score))
            
            print('  % 8.4f   % 8.4f   % 8.4f      % 8.4f   % 8.4f    % 8.4f   % 8.4f' % 
                  (phi, f_val, m4_factor, w_scf, omega_scf, mass_ratio, score))
            
        except Exception as e:
            print('  % 8.4f   % 8.4f   % 8.4f      ERROR: %s' % (phi, f_val, m4_factor, str(e)[:25]))
        
        os.unlink(tmp_ini.name)

    print()
    if results:
        # Sort by score (lower is better)
        results.sort(key=lambda x: x[6])
        
        print('TOP 5 BEST MATCHES:')
        print()
        for rank, (phi, f_val, m4_factor, w, omega, mass_r, score) in enumerate(results[:5], 1):
            m4_val = m4_orig * m4_factor
            print('Rank %d: Score = %.4f' % (rank, score))
            print('  scf_phi_ini = %.4f' % phi)
            print('  scf_f = %.4f' % f_val)
            print('  scf_M4 = %.6e (factor: %.4f)' % (m4_val, m4_factor))
            print('  w_scf(z=0) = %.6f (target: %.2f, OK: %s)' % (w, args.target_w, 'YES' if w > -0.95 else 'NO'))
            print('  Omega_scf(z=0) = %.6f (target: %.2f)' % (omega, args.target_omega))
            print('  V\'\'(phi)/H0^2 = %.4f (thawing regime: %s)' % (mass_r, 'YES' if 0.5 < mass_r < 5.0 else 'POSSIBLY'))
            print()
    else:
        print('No successful runs.')
        sys.exit(1)

if __name__ == '__main__':
    main()
