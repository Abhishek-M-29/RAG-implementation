import subprocess
python = r'.venv\Scripts\python.exe'
print("Running mini test...")
try:
    result = subprocess.run([python, 'main.py'], input='invalid\n', capture_output=True, text=True, timeout=10)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
except Exception as e:
    print("Exception:", e)
