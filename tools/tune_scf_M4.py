#!/usr/bin/env python3
"""
Tune scf_M4 in a CLASS .ini to reach a target Omega_scf(today).

Usage: python tools/tune_scf_M4.py [--ini mytest.ini] [--class ./class] [--target 0.688]

The script makes a temporary copy of the ini, updates `scf_M4`, runs CLASS,
parses the most recent `*_background.dat` output to compute Omega_scf = rho_scf/rho_crit
at the final row (z ~ 0), and bisects scf_M4 until the target is reached.

Note: adjust `CLASS_BIN` if your CLASS executable is not `./class`.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from math import log10


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
        # append at end
        with open(dst, "a") as f_out:
            f_out.write("\n%s = %g\n" % (key, value))


def write_ini_with_string(src, dst, key, value):
    """Write or replace a string-valued key in an ini file (preserve other lines).
    If key exists its line is replaced, otherwise appended at end."""
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


def create_temp_ini_with_overrides(src_ini, dst_ini, num_overrides=None, str_overrides=None):
    """Copy src_ini to dst_ini and apply numeric and string overrides.
    Only the provided keys are changed; all other lines are preserved.
    This ensures SCF parameters from the original ini remain intact."""
    if num_overrides is None:
        num_overrides = {}
    if str_overrides is None:
        str_overrides = {}

    # Start with a direct copy
    shutil.copyfile(src_ini, dst_ini)

    # Apply numeric overrides one by one using safe tempfile then replace
    for k, v in num_overrides.items():
        tmp = dst_ini + '.tmp'
        write_ini_with_value(dst_ini, tmp, k, v)
        os.replace(tmp, dst_ini)

    # Apply string overrides similarly
    for k, v in str_overrides.items():
        tmp = dst_ini + '.tmp'
        write_ini_with_string(dst_ini, tmp, k, v)
        os.replace(tmp, dst_ini)


def run_class(class_bin, ini_path, timeout=120):
    # Run CLASS from the repository root (directory containing the CLASS binary)
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
        # also check output/ folder
        files = glob.glob(os.path.join("output", "*_background.dat"))
    if not files:
        return None
    files.sort(key=os.path.getmtime)
    return files[-1]


def parse_background_for_omega(path):
    # Read file and find header line with column titles
    with open(path) as f:
        lines = f.readlines()

    header = None
    header_idx = None
    for i in range(min(50, len(lines))):
        line = lines[i].strip()
        if not line:
            continue
        # remove leading comment marker if present
        if line.startswith('#'):
            txt = line.lstrip('#').strip()
        elif line.startswith('"'):
            txt = line.lstrip('"').strip()
        else:
            txt = line
        tokens = txt.split()
        # look for at least the three required columns in the header
        if any('(.)rho_scf' == t for t in tokens) or any('rho_scf' in t for t in tokens):
            if any('(.)rho_crit' == t for t in tokens) or any('rho_crit' in t for t in tokens):
                if any('(.)z' == t for t in tokens) or any('z' == t for t in tokens) or any('(z)' == t for t in tokens):
                    header = tokens
                    header_idx = i
                    break

    if header is None:
        raise RuntimeError('Could not find header with required columns in %s' % path)

    titles = header

    # find exact matches first, otherwise fall back to substring matches
    def find_index(exact_name, substr=None):
        if exact_name in titles:
            return titles.index(exact_name)
        if substr is not None:
            for j, t in enumerate(titles):
                if substr in t:
                    return j
        raise RuntimeError('Could not find column %s in header' % exact_name)

    i_rho_scf = find_index('(.)rho_scf', 'rho_scf')
    i_rho_crit = find_index('(.)rho_crit', 'rho_crit')
    # accept '(.)z' or 'z' or '(z)'
    try:
        i_z = find_index('(.)z', 'z')
    except RuntimeError:
        # if z not found, try any token that equals 'z' or contains 'z'
        i_z = next(j for j, t in enumerate(titles) if t == 'z' or '(z)' == t or 'z' in t)

    # collect data rows after header
    data_lines = [ln for ln in lines[header_idx+1:] if ln.strip() and not ln.strip().startswith('#')]
    if not data_lines:
        raise RuntimeError('No data rows found in %s' % path)

    # parse rows and find the one with z closest to 0
    best_row = None
    best_z_diff = None
    for ln in data_lines:
        parts = ln.split()
        # skip short rows
        if len(parts) <= max(i_rho_scf, i_rho_crit, i_z):
            continue
        try:
            zval = float(parts[i_z])
            rho_scf = float(parts[i_rho_scf])
            rho_crit = float(parts[i_rho_crit])
        except Exception:
            continue
        diff = abs(zval - 0.0)
        if best_z_diff is None or diff < best_z_diff:
            best_z_diff = diff
            best_row = (rho_scf, rho_crit)

    if best_row is None:
        raise RuntimeError('Could not find a valid data row with required columns in %s' % path)

    rho_scf, rho_crit = best_row
    return rho_scf / rho_crit


def bisect_scf_M4(class_bin, ini_orig, key, target, phi_ini=None, m4_min=None, m4_max=None, tol=1e-3, maxiter=25):
    # initial bracket: use provided bounds m4_min and m4_max
    if m4_min is None or m4_max is None:
        cur = read_ini_value(ini_orig, key)
        if cur is None:
            raise RuntimeError('Could not read %s from %s' % (key, ini_orig))
        # fallback defaults
        m4_min = cur * 1e-2
        m4_max = cur * 1e2

    lo = float(m4_min)
    hi = float(m4_max)
    if lo <= 0 or hi <= 0 or hi <= lo:
        raise RuntimeError('Invalid initial bracket: m4_min=%g m4_max=%g' % (lo, hi))

    # Ensure both ends produce successful CLASS runs and obtain their Omega values.
    def try_run(val):
        tmp_ini = tempfile.NamedTemporaryFile(delete=False, suffix='.ini')
        tmp_ini.close()
        # Copy the original ini into the temp file and only override scf_M4 and root
        overrides_num = {key: val}
        if phi_ini is not None:
            overrides_num['scf_phi_ini'] = phi_ini
        overrides_str = {'root': 'output/tune_'}
        create_temp_ini_with_overrides(ini_orig, tmp_ini.name, num_overrides=overrides_num, str_overrides=overrides_str)
        ok = run_class(class_bin, tmp_ini.name)
        if not ok:
            os.unlink(tmp_ini.name)
            return None
        bg = find_latest_background_file()
        if bg is None:
            os.unlink(tmp_ini.name)
            return None
        try:
            omega = parse_background_for_omega(bg)
        except Exception:
            os.unlink(tmp_ini.name)
            return None
        os.unlink(tmp_ini.name)
        return omega

    # Try initial lo/hi; if runs fail, adjust bracket: increase lo (make larger) if too-small values fail,
    # decrease hi (make smaller) if too-large values fail. Try limited attempts.
    max_adjust = 20
    omega_lo = try_run(lo)
    attempts = 0
    while omega_lo is None and attempts < max_adjust:
        lo *= 10.0
        omega_lo = try_run(lo)
        attempts += 1
    if omega_lo is None:
        raise RuntimeError('Could not get successful CLASS run for lower bound after adjustments')

    omega_hi = try_run(hi)
    attempts = 0
    while omega_hi is None and attempts < max_adjust:
        hi /= 10.0
        if hi <= 0:
            break
        omega_hi = try_run(hi)
        attempts += 1
    if omega_hi is None:
        raise RuntimeError('Could not get successful CLASS run for upper bound after adjustments')

    # Now ensure target is bracketed between omega_lo and omega_hi. If not, expand accordingly.
    # We assume monotonic increase of Omega with scf_M4.
    expand_attempts = 0
    while not (min(omega_lo, omega_hi) <= target <= max(omega_lo, omega_hi)) and expand_attempts < 50:
        # If both below target, increase hi
        if omega_lo < target and omega_hi < target:
            hi *= 10.0
            omega_hi = try_run(hi)
            if omega_hi is None:
                # if fail, try smaller expansion step
                hi /= 10.0
                hi *= 2.0
                omega_hi = try_run(hi)
        # If both above target, decrease lo
        elif omega_lo > target and omega_hi > target:
            lo /= 10.0
            omega_lo = try_run(lo)
            if omega_lo is None:
                lo *= 5.0
                omega_lo = try_run(lo)
        else:
            break
        expand_attempts += 1
    if not (min(omega_lo, omega_hi) <= target <= max(omega_lo, omega_hi)):
        raise RuntimeError('Could not bracket target Omega after expansion: omega_lo=%g omega_hi=%g' % (omega_lo, omega_hi))

    # bisection in log space for scf_M4
    for it in range(maxiter):
        mid = 10 ** ((log10(lo) + log10(hi)) / 2.0)
        tmp_ini = tempfile.NamedTemporaryFile(delete=False, suffix='.ini')
        tmp_ini.close()
        # Copy the original ini into the temp file and only override scf_M4 and root
        overrides_num = {key: mid}
        if phi_ini is not None:
            overrides_num['scf_phi_ini'] = phi_ini
        overrides_str = {'root': 'output/tune_'}
        create_temp_ini_with_overrides(ini_orig, tmp_ini.name, num_overrides=overrides_num, str_overrides=overrides_str)
        ok = run_class(class_bin, tmp_ini.name)
        if not ok:
            os.unlink(tmp_ini.name)
            raise RuntimeError('CLASS run failed for %s=%g' % (key, mid))
        bg = find_latest_background_file()
        if bg is None:
            os.unlink(tmp_ini.name)
            raise RuntimeError('No background output produced')
        omega_mid = parse_background_for_omega(bg)
        os.unlink(tmp_ini.name)
        print('iter %d: %g -> Omega=%g' % (it, mid, omega_mid))
        if abs(omega_mid - target) < tol:
            return mid, omega_mid
        if omega_mid < target:
            lo = mid
        else:
            hi = mid
    return mid, omega_mid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ini', default='mytest.ini')
    ap.add_argument('--class', dest='class_bin', default='./class')
    ap.add_argument('--target', type=float, default=0.688)
    ap.add_argument('--phi_ini', type=float, default=None,
                    help='optional scf_phi_ini to set in the ini')
    ap.add_argument('--m4-min', type=float, default=None,
                    help='optional minimum scf_M4 bracket')
    ap.add_argument('--m4-max', type=float, default=None,
                    help='optional maximum scf_M4 bracket')
    args = ap.parse_args()

    key = 'scf_M4'
    try:
        best, omega = bisect_scf_M4(args.class_bin, args.ini, key, args.target,
                                    phi_ini=args.phi_ini, m4_min=args.m4_min, m4_max=args.m4_max)
    except Exception as e:
        print('Error:', e)
        sys.exit(1)
    print('Found scf_M4 = %g -> Omega_scf = %g' % (best, omega))
    print('Updating %s with this value.' % args.ini)
    # Backup original
    shutil.copyfile(args.ini, args.ini + '.bak')
    write_ini_with_value(args.ini + '.bak', args.ini, key, best)


if __name__ == '__main__':
    main()
