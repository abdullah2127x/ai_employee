import subprocess

# result = subprocess.run(
#     ["ccr", "code", "-p", "Hi"],
#     shell=True,
#     capture_output=True,  # capture stdout and stderr
#     text=True,  # return strings, not bytes || replacement of .decode('utf-8')
#     timeout=300,  # give up after 5 minutes
#     # cwd="/path/to/vault",
# )
CLAUDE_COMMAND = ["qwen"]

cmd = CLAUDE_COMMAND + ["-p", "Hi"]


result = subprocess.run(
            cmd,
            shell=True,           # Required on Windows for .cmd wrappers
            capture_output=True,  # Capture stdout and stderr
            text=True,            # Return strings, not bytes
            timeout=60,      # Give up after timeout seconds
        )
print("Return code:", result.returncode)
print("Stdout:", result.stdout)
print("Stderr:", result.stderr)
