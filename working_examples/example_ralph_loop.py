import subprocess

prompt = "Explain recursion simply."

for i in range(5):
    result = subprocess.run(
        ["ccr","code", "-p", prompt],
        capture_output=True,
        shell=True,
        text=True
    )
    
    output = result.stdout.strip()
    print(f"\n--- Iteration {i+1} ---\n{output}")
    
    # Feed output back in
    prompt = output