import subprocess
result = subprocess.run(['venv/Scripts/pytest.exe', 'tests/test_security.py', '--junitxml=report.xml'])
print("Exit code:", result.returncode)
