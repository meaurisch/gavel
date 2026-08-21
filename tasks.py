"""Uniform entry points: python tasks.py test|run|check (studio convention)."""
import subprocess
import sys

def test():
    rc = subprocess.call([sys.executable, "-m", "pytest", "-q"])
    # pytest exit 5 = no tests collected - green until first test exists
    return 0 if rc == 5 else rc
def run():   print("no run target yet"); return 0
def check(): return test()

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    sys.exit({"test": test, "run": run, "check": check}[cmd]())
