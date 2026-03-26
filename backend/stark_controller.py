import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class StarkController:
    def __init__(self, project_root):
        self.project_root = Path(project_root).resolve()
        self.script_path = self.project_root / "hand_gesture_test.py"
        self.log_path = self.project_root / ".cache" / "stark_mode.log"
        self.process = None

    def is_active(self):
        return self.process is not None and self.process.poll() is None

    def start(self, show_preview=False, mode="hand"):
        if self.is_active():
            return True, "Stark mode is already active."

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = self.log_path.open("a", encoding="utf-8")
        log_handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Stark mode\n")
        log_handle.flush()

        normalized_mode = "advanced" if str(mode).strip().lower() == "advanced" else "hand"
        command = [sys.executable, str(self.script_path), "--headless", "--mode", normalized_mode]
        if show_preview:
            command = [sys.executable, str(self.script_path), "--show-preview", "--mode", normalized_mode]

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )
        except Exception as exc:
            log_handle.write(f"Failed to spawn Stark mode: {exc}\n")
            log_handle.close()
            self.process = None
            return False, f"Failed to start Stark mode: {exc}"

        time.sleep(1.2)
        if self.process.poll() is not None:
            code = self.process.returncode
            log_handle.write(f"Stark mode exited during startup with code {code}\n")
            log_handle.close()
            self.process = None
            return False, (
                "Stark mode failed to stay alive during startup. "
                f"See {self.log_path} for details."
            )

        log_handle.write("Stark mode is running\n")
        log_handle.flush()
        log_handle.close()
        label = "Advanced Stark mode" if normalized_mode == "advanced" else "Stark mode"
        return True, f"{label} activated."

    def stop(self):
        if not self.process:
            return True, "Stark mode is already inactive."

        if self.process.poll() is not None:
            self.process = None
            return True, "Stark mode is already inactive."

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait(timeout=2)
            except Exception as exc:
                return False, f"Failed to force-stop Stark mode: {exc}"
        except ProcessLookupError:
            pass
        except Exception as exc:
            return False, f"Failed to stop Stark mode: {exc}"
        finally:
            self.process = None

        return True, "Stark mode deactivated."
