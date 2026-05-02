import subprocess
import sys

python = r'.venv\Scripts\python.exe'
tests = []

# === TEST 1: Empty input on menu ===
print('='*60, flush=True)
print('TEST 1: Empty input on main menu', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('STDERR:', result.stderr[-200:] if result.stderr else 'None', flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Empty menu input', 'PASS' if 'Invalid action' in result.stdout else 'FAIL'))

# === TEST 2: SQL injection in menu ===
print('\n' + '='*60, flush=True)
print('TEST 2: SQL injection in menu choice', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input="'; DROP TABLE users; --\n", capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('SQL injection menu', 'PASS' if 'Invalid action' in result.stdout else 'FAIL'))

# === TEST 3: Path traversal in index directory ===
print('\n' + '='*60, flush=True)
print('TEST 3: Path traversal in index directory input', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\n..\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
# This SHOULD either find no PDFs or handle gracefully - but it SHOULDN'T crash
traversal_pass = result.returncode == 0 or 'No PDF files found' in result.stdout or 'Error' in result.stdout
tests.append(('Path traversal', 'PASS (but unvalidated!)' if traversal_pass else 'FAIL'))

# === TEST 4: Null byte injection in directory ===
print('\n' + '='*60, flush=True)
print('TEST 4: Null byte injection in directory path', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\ndata\x00../../etc/passwd\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Null byte injection', 'PASS' if result.returncode == 0 or 'Error' in result.stdout else 'FAIL'))

# === TEST 5: Very long input (buffer overflow attempt) ===
print('\n' + '='*60, flush=True)
print('TEST 5: Very long input string', flush=True)
print('='*60, flush=True)
long_input = 'A' * 10000
result = subprocess.run([python, 'main.py'], input=f'index\n{long_input}\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout[:300], flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Long input overflow', 'PASS' if result.returncode == 0 or 'Error' in result.stdout or 'not found' in result.stdout else 'FAIL'))

# === TEST 6: Command injection in directory path ===
print('\n' + '='*60, flush=True)
print('TEST 6: Command injection in directory path', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\n; rm -rf / #\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Command injection dir', 'PASS' if 'not found' in result.stdout or 'Error' in result.stdout or 'not a directory' in result.stdout else 'FAIL'))

# === TEST 7: Empty directory path ===
print('\n' + '='*60, flush=True)
print('TEST 7: Empty directory path for indexing', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\n\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Empty directory path', 'PASS' if 'No source directory' in result.stdout else 'FAIL'))

# === TEST 8: Query with no index ===
print('\n' + '='*60, flush=True)
print('TEST 8: Query pipeline with no existing index', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='query\nWhat is life?\n\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Query no index', 'PASS' if 'Failed to load' in result.stdout or 'not found' in result.stdout else 'FAIL'))

# === TEST 9: Special chars & unicode in menu ===
print('\n' + '='*60, flush=True)
print('TEST 9: Unicode/special chars in input', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\n<script>alert(1)</script>\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('XSS-like input', 'PASS' if 'not found' in result.stdout or 'Error' in result.stdout or 'not a directory' in result.stdout else 'FAIL'))

# === TEST 10: Pipe operator injection ===
print('\n' + '='*60, flush=True)
print('TEST 10: Pipe/shell operator injection in path', flush=True)
print('='*60, flush=True)
result = subprocess.run([python, 'main.py'], input='index\ndata | whoami\n', capture_output=True, text=True, timeout=300)
print('STDOUT:', result.stdout, flush=True)
print('EXIT CODE:', result.returncode, flush=True)
tests.append(('Pipe injection', 'PASS' if 'not found' in result.stdout or 'Error' in result.stdout or 'not a directory' in result.stdout else 'FAIL'))

# === SUMMARY ===
print('\n' + '='*60)
print('INJECTION TEST SUMMARY')
print('='*60)
for name, status in tests:
    icon = '✓' if 'PASS' in status else '✗'
    print(f'  {icon} {name}: {status}')
print(f'\nTotal: {sum(1 for _,s in tests if "PASS" in s)}/{len(tests)} passed')
