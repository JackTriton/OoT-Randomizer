#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import argparse
import json
import platform
import re
import shutil
from subprocess import check_call as call, CalledProcessError, run, PIPE
from rom_diff import create_diff
from ntype import BigStream
from crc import calculate_crc


def add_existing_path_entries(*paths):
    entries = [path for path in paths if path and os.path.isdir(path)]
    if entries:
        os.environ['PATH'] = os.pathsep.join(entries + [os.environ.get('PATH', '')])


def find_executable(name):
    return shutil.which(name)


def resolve_make_command(requested):
    if requested and requested != 'auto':
        resolved = find_executable(requested)
        return requested, resolved

    env_make = os.environ.get('MAKE')
    candidates = []
    if env_make:
        candidates.append(env_make)
    # Homebrew's GNU make is installed as gmake. Prefer it when available,
    # because macOS /usr/bin/make is BSD make and cannot parse this Makefile.
    candidates.extend(['gmake', 'make'])

    for candidate in candidates:
        resolved = find_executable(candidate)
        if resolved:
            return candidate, resolved
    return 'make', None


def mips_tool_names(prefix):
    return {
        'CC': f'{prefix}gcc',
        'LD': f'{prefix}ld',
        'OBJDUMP': f'{prefix}objdump',
        'OBJCOPY': f'{prefix}objcopy',
    }


def find_mips_toolchain(prefix):
    tools = mips_tool_names(prefix)
    resolved = {kind: find_executable(name) for kind, name in tools.items()}
    return tools, resolved, all(resolved.values())



MIPS_STANDARD_HEADER_PROBE = [
    'assert.h', 'complex.h', 'ctype.h', 'errno.h', 'fenv.h', 'float.h',
    'inttypes.h', 'iso646.h', 'limits.h', 'locale.h', 'math.h', 'setjmp.h',
    'signal.h', 'stdalign.h', 'stdarg.h', 'stdatomic.h', 'stdbool.h',
    'stddef.h', 'stdint.h', 'stdio.h', 'stdlib.h', 'stdnoreturn.h',
    'string.h', 'tgmath.h', 'time.h', 'uchar.h', 'wchar.h', 'wctype.h',
]


def check_mips_standard_headers(cc_path):
    if not cc_path:
        return False, 'missing compiler'
    probe = ''.join(f'#include <{header}>\n' for header in MIPS_STANDARD_HEADER_PROBE)
    try:
        result = run([cc_path, '-E', '-xc', '-'], input=probe, text=True, stdout=PIPE, stderr=PIPE)
    except OSError as e:
        return False, str(e)
    if result.returncode == 0:
        return True, ''
    detail = (result.stderr or result.stdout or '').strip()
    return False, detail.splitlines()[-1] if detail else f'exit status {result.returncode}'

def print_toolchain_check(root_dir, tools_dir, make_command, make_path, mips_prefix):
    print('OoTR ASM toolchain check')
    print(f'  host: {platform.platform()} / {platform.machine()}')
    print(f'  ASM dir: {root_dir}')
    print(f'  tools dir: {tools_dir}')
    print(f'  armips: {find_executable("armips") or "missing"}')
    print(f'  GNU make: {make_path or "missing"} ({make_command})')

    if platform.system() == 'Darwin' and os.path.basename(make_path or '') == 'make' and make_path == '/usr/bin/make':
        print('    warning: /usr/bin/make is BSD make. Install Homebrew make and use gmake.')

    tools, resolved, ok = find_mips_toolchain(mips_prefix)
    print(f'  MIPS prefix: {mips_prefix}')
    for kind in ('CC', 'LD', 'OBJDUMP', 'OBJCOPY'):
        name = tools[kind]
        print(f'    {name:<24} {resolved[kind] or "missing"}')
    print(f'  selected MIPS toolchain: {"ok" if ok else "missing"}')
    headers_ok = False
    if ok:
        headers_ok, headers_detail = check_mips_standard_headers(resolved['CC'])
        print(f'  MIPS C standard headers: {"ok" if headers_ok else "missing"}')
        if not headers_ok and headers_detail:
            print(f'    {headers_detail}')
    else:
        print('  MIPS C standard headers: skipped')

    ok = ok and (headers_ok if ok else False)

    if not ok:
        print('\nSuggested fixes:')
        print('  - Put a glankk/n64 toolchain at ASM/tools/n64, or add its bin directory to PATH.')
        print('  - On macOS Apple Silicon, use a glankk/n64 version with Apple Silicon toolchain support.')
        print('  - Then run: python3 ASM/build.py --check-toolchain')
        print('  - If C standard headers are missing after building n64, update n64 and run gmake install-sys again.')
    return ok


parser = argparse.ArgumentParser()
parser.add_argument('--pj64sym', help="Output path for Project64 debugging symbols")
parser.add_argument('--compile-c', action='store_true', help="Recompile C modules. This is the default")
parser.add_argument('--no-compile-c', action='store_true', help="Do not recompile C modules")
parser.add_argument('--dump-obj', action='store_true', help="Dumps extra object info for debugging purposes. Does nothing with --no-compile-c")
parser.add_argument('--diff-only', action='store_true', help="Creates diff output without running armips")
parser.add_argument('--mips-binutils-prefix', type=str, default="mips64-", help="Use a different prefix for N64 toolchain")
parser.add_argument('--make-command', type=str, default='auto', help="GNU make command to use for C modules. Defaults to auto, preferring gmake when available.")
parser.add_argument('--check-toolchain', action='store_true', help="Check whether armips, GNU make, and the MIPS64 toolchain are visible")
parser.add_argument('--debug-c', action='store_true', help="Define DEBUG_MODE 1 for C modules")

args = parser.parse_args()
pj64_sym_path = args.pj64sym
compile_c = not args.no_compile_c
dump_obj = args.dump_obj
diff_only = args.diff_only
mips_binutils_prefix = args.mips_binutils_prefix
debug_c = args.debug_c

root_dir = os.path.dirname(os.path.realpath(__file__))
tools_dir = os.path.join(root_dir, 'tools')
# Makes it possible to use the "tools" directory as the prefix for the toolchain
tools_bin_dir = os.path.join(tools_dir, 'bin')
# Makes it possible to copy the full toolchain prefix into the "tools" directory
n64_bin_dir = os.path.join(tools_dir, "n64", "bin")
add_existing_path_entries(tools_dir, tools_bin_dir, n64_bin_dir)

make_command, make_path = resolve_make_command(args.make_command)

if args.check_toolchain:
    ok = True
    ok = print_toolchain_check(root_dir, tools_dir, make_command, make_path, mips_binutils_prefix) and ok
    if not find_executable('armips'):
        ok = False
    if not make_path:
        ok = False
    if platform.system() == 'Darwin' and make_path == '/usr/bin/make':
        ok = False
    sys.exit(0 if ok else 1)

run_dir = root_dir

# Compile code

os.chdir(run_dir)

base_rom_size = os.stat('roms/base.z64').st_size
if base_rom_size != 0x400_0000:
    sys.exit(f'build.py: roms/base.z64 should be 0x4000000 bytes (64 MiB), but yours is 0x{base_rom_size:x} bytes ({base_rom_size / (1024 ** 2)} MiB). Make sure you have an uncompressed base ROM (see ../bin/Decompress).')

if compile_c:
    if not make_path:
        sys.exit('build.py: GNU make was not found. Install GNU make (gmake on macOS) or pass --make-command.')
    if platform.system() == 'Darwin' and make_path == '/usr/bin/make':
        sys.exit('build.py: /usr/bin/make is BSD make and cannot build ASM/Makefile. Install Homebrew make and re-run with gmake in PATH.')
    _, mips_tools, mips_ok = find_mips_toolchain(mips_binutils_prefix)
    if not mips_ok:
        missing = ', '.join(kind for kind, path in mips_tools.items() if not path)
        sys.exit(f'build.py: missing MIPS64 toolchain components for prefix {mips_binutils_prefix!r}: {missing}. Run python3 ASM/build.py --check-toolchain for details.')
    headers_ok, headers_detail = check_mips_standard_headers(mips_tools['CC'])
    if not headers_ok:
        detail = f' ({headers_detail})' if headers_detail else ''
        sys.exit(f'build.py: MIPS64 C standard headers are not usable{detail}. Run gmake install-sys for the n64 toolchain, then re-run python3 ASM/build.py --check-toolchain.')

    clist = [make_command]
    clist.append(f'MIPS_BINUTILS_PREFIX={mips_binutils_prefix}')
    if debug_c:
        clist.append(f'DEBUG_MODE=1')
    if dump_obj:
        clist.append('RUN_OBJDUMP=1')
    try:
        call(clist)
    except CalledProcessError as e:
        print(e.output)
        exit(e.returncode)

if not diff_only:
    if not find_executable('armips'):
        sys.exit('build.py: armips was not found. Put armips in ASM/tools or add it to PATH.')
    os.chdir(run_dir + '/src')
    call(['armips', '-sym2', '../build/asm_symbols.txt', 'build.asm'])

os.chdir(run_dir)

with open('build/asm_symbols.txt', 'rb') as f:
    asm_symbols_content = f.read()
asm_symbols_content = asm_symbols_content.replace(b'\r\n', b'\n')
asm_symbols_content = asm_symbols_content.replace(b'\x1A', b'')
with open('build/asm_symbols.txt', 'wb') as f:
    f.write(asm_symbols_content)

# Parse symbols

c_sym_types = {}

with open('build/c_symbols.txt', 'r') as f:
    for line in f:
        m = re.match(r'''
                ^
                [0-9a-fA-F]+
                .*
                \.
                ([^\s]+)
                \s+
                [0-9a-fA-F]+
                \s+
                ([^.$][^\s]+)
                \s+$
            ''', line, re.VERBOSE)
        if m:
            sym_type = m.group(1)
            name = m.group(2)
            c_sym_types[name] = 'code' if sym_type == 'text' else 'data'

symbols = {}

with open('build/asm_symbols.txt', 'r') as f:
    for line in f:
        parts = line.strip().split(' ')
        if len(parts) < 2:
            continue
        address, sym_name = parts
        if address[0] != '8':
            continue
        if sym_name[0] in ['.', '@']:
            continue
        sym_type = c_sym_types.get(sym_name) or ('data' if sym_name.isupper() else 'code')
        symbols[sym_name] = {
            'type': sym_type,
            'address': address,
        }

# Loop through a second time, add lengths to each data symbol
# This could probably be optimized to run in a single pass :)
with open('build/asm_symbols.txt', 'r') as f:
    for line in f:
        parts = line.strip().split(' ')
        if len(parts) < 2:
            continue
        address, sym_name = parts
        if sym_name.startswith('.'):
            # split on the ':' to get the length, in hex
            type, hex_length = sym_name.split(':')
            for symbol, sym_data in symbols.items():
                if sym_data['address'] == address and sym_data['type'] == 'data':
                    sym_data['length'] = int(hex_length, 16)

# Output symbols

os.chdir(run_dir)

PAYLOAD_START = int(symbols['PAYLOAD_START']['address'], 16)
PAYLOAD_END = int(symbols['PAYLOAD_END']['address'], 16)
data_symbols = {}
patch_symbols = {}
for (name, sym) in symbols.items():
    if sym['type'] == 'data':
        addr = int(sym['address'], 16)
        if PAYLOAD_START <= addr < PAYLOAD_END:
            addr = addr - 0x80400000 + 0x03480000
            data_symbols[name] = {
                'address': f'{addr:08X}',
                'length': sym.get('length', 0),
            }
        else:
            patch_symbols[name] = addr

with open('../data/generated/symbols.json', 'w', newline='\n') as f:
    json.dump(data_symbols, f, indent=4, sort_keys=True)

with open('../data/generated/patch_symbols.json', 'w', newline='\n') as f:
    json.dump(patch_symbols, f, indent=4, sort_keys=True)

if pj64_sym_path:
    pj64_sym_path = os.path.realpath(pj64_sym_path)
    with open(pj64_sym_path, 'w') as f:
        key = lambda pair: pair[1]['address']
        for sym_name, sym in sorted(symbols.items(), key=key):
            f.write('{0},{1},{2}\n'.format(sym['address'], sym['type'], sym_name))


with open('roms/patched.z64', 'r+b') as stream:
    buffer = bytearray(stream.read(0x101000))
    crc = calculate_crc(BigStream(buffer))
    stream.seek(0x10)
    stream.write(bytearray(crc))

# Diff ROMs
create_diff('roms/base.z64', 'roms/patched.z64', '../data/generated/rom_patch.txt')
