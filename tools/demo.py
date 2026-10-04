"""Run the fictional lifecycle in isolation; never use the caller's archives."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="ripper-demo-") as directory:
        home = Path(directory)
        environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
                       "RIPPER_OUTPUT_DIR": str(home / "output")}
        def run(*args):
            result = subprocess.run([sys.executable, str(ROOT / "ripper/scripts/ripper.py"), *args],
                                    env=environment, capture_output=True, text=True, encoding="utf-8")
            if result.returncode != 0:
                raise RuntimeError(result.stderr)
            return json.loads(result.stdout)
        example = ROOT / "examples/task-recovery"
        deposit = run("deposit", "Fictional Task Recovery", "--analysis", str(example / "analysis.json"),
                      "--source", str(example / "project.md"))
        claim = run("browse")["usable_claims"][0]
        run("confirm", deposit["project_id"], claim["id"], "--question", "Was this deployed to production?",
            "--answer", "No. This is a fictional design demonstration.", "--status", "rejected",
            "--revision", str(claim["revision"]))
        run("rebuild")
        exported = run("export", "star", "Reliability Engineer")
        run("verify-export", exported["manifest_path"])
        print("Demo passed: deposit → confirm → rebuild → export → verify\n")
        print(Path(exported["output_path"]).read_text(encoding="utf-8"))
        print("Temporary demo archives and outputs are removed on exit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
