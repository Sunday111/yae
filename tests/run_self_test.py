from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


def main() -> None:
    yae_root = Path(__file__).resolve().parents[1]
    fixture_dir = yae_root / "tests" / "fixtures" / "minimal_project"
    external_modules_dir = yae_root / ".cache" / "self-test-repositories"

    with tempfile.TemporaryDirectory(prefix="yae-self-test-") as temp_dir:
        project_dir = Path(temp_dir) / "minimal_project"
        shutil.copytree(fixture_dir, project_dir)

        yae = (yae_root / "yae").as_posix()
        external_arg = f"--external_modules_dir={external_modules_dir}"

        list_result = run([yae, "list", external_arg], cwd=project_dir)
        expected_modules = {
            "project  executable self_test_app",
            "project  library    self_test_lib",
        }
        listed_modules = {
            line for line in list_result.stdout.splitlines() if line.startswith(("project ", "support ", "external "))
        }
        if listed_modules != expected_modules:
            raise RuntimeError(f"Unexpected default list output:\n{list_result.stdout}")

        run([yae, "configure", external_arg], cwd=project_dir)
        run([yae, "build", external_arg], cwd=project_dir)

        content_file = project_dir / "build" / "bin" / "content" / "self_test.txt"
        if content_file.read_text(encoding="utf-8").strip() != "content copied":
            raise RuntimeError(f"Expected copied content at {content_file}")


if __name__ == "__main__":
    main()
