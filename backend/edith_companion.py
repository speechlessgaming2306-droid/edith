import argparse
import os
import subprocess
import sys
from pathlib import Path

import socketio


def _normalize_mac_app_name(app_name: str) -> str:
    lowered = (app_name or "").strip().lower()
    aliases = {
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "safari": "Safari",
        "finder": "Finder",
        "terminal": "Terminal",
        "notes": "Notes",
        "spotify": "Spotify",
        "mail": "Mail",
        "messages": "Messages",
        "whatsapp": "WhatsApp",
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
    }
    return aliases.get(lowered, app_name)


def _resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _handle_open_mac_app(payload: dict) -> str:
    app_name = str(payload.get("app_name") or "").strip()
    if not app_name:
        raise ValueError("app_name is required.")
    subprocess.run(["open", "-a", _normalize_mac_app_name(app_name)], check=True)
    return f"Opened '{app_name}'."


def _handle_close_mac_app(payload: dict) -> str:
    app_name = str(payload.get("app_name") or "").strip()
    if not app_name:
        raise ValueError("app_name is required.")
    subprocess.run(
        ["osascript", "-e", f'tell application "{_normalize_mac_app_name(app_name)}" to quit'],
        check=True,
        capture_output=True,
        text=True,
    )
    return f"Closed '{app_name}'."


def _handle_read_clipboard(_: dict) -> str:
    result = subprocess.run(["pbpaste"], check=True, capture_output=True, text=True)
    text = result.stdout or ""
    if not text.strip():
        return "The clipboard is currently empty."
    return f"Clipboard contents:\n{text}"


def _handle_copy_to_clipboard(payload: dict) -> str:
    subprocess.run(["pbcopy"], input=str(payload.get("text") or ""), check=True, text=True)
    return "Copied to the clipboard."


def _handle_list_mac_printers(_: dict) -> str:
    printers_proc = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, check=True)
    default_proc = subprocess.run(["lpstat", "-d"], capture_output=True, text=True, check=False)

    printer_lines = [line.strip() for line in printers_proc.stdout.splitlines() if line.strip()]
    printers = []
    for line in printer_lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "printer":
            printers.append(parts[1])

    default_line = (default_proc.stdout or "").strip()
    default_printer = None
    if "system default destination:" in default_line.lower():
        default_printer = default_line.split(":", 1)[-1].strip()

    if not printers:
        return "No printers were found on this Mac."

    summary = f"Available printers: {', '.join(printers)}."
    if default_printer:
        summary += f" Default printer: {default_printer}."
    return summary


def _handle_print_file(payload: dict) -> str:
    file_path = _resolve_path(str(payload.get("path") or ""))
    if not file_path.exists():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")

    printer_name = str(payload.get("printer_name") or "").strip() or None
    copies = int(payload.get("copies") or 1)
    command = ["lp"]
    if printer_name:
        command += ["-d", printer_name]
    if copies > 1:
        command += ["-n", str(copies)]
    command.append(str(file_path))

    proc = subprocess.run(command, capture_output=True, text=True, check=True)
    output = (proc.stdout or "").strip()
    target = f" on printer '{printer_name}'" if printer_name else ""
    return f"Sent '{file_path.name}' to print{target}.{f' {output}' if output else ''}"


def _handle_open_file(payload: dict) -> str:
    file_path = _resolve_path(str(payload.get("path") or ""))
    if not file_path.exists():
        raise FileNotFoundError(f"File '{file_path}' does not exist.")

    if file_path.suffix.lower() in {".html", ".htm", ".pdf"}:
        subprocess.run(["open", "-a", "Google Chrome", str(file_path)], check=True)
        return f"Opened '{file_path.name}' in Google Chrome."

    subprocess.run(["open", str(file_path)], check=True)
    return f"Opened '{file_path.name}'."


ACTION_HANDLERS = {
    "open_mac_app": _handle_open_mac_app,
    "close_mac_app": _handle_close_mac_app,
    "read_clipboard": _handle_read_clipboard,
    "copy_to_clipboard": _handle_copy_to_clipboard,
    "list_mac_printers": _handle_list_mac_printers,
    "print_file": _handle_print_file,
    "open_file": _handle_open_file,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Edith local companion for hosted backends.")
    parser.add_argument("--server", default=os.getenv("EDITH_SERVER_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("EDITH_COMPANION_TOKEN", ""))
    parser.add_argument("--id", dest="companion_id", default=os.getenv("EDITH_COMPANION_ID", "primary-mac"))
    parser.add_argument("--name", default=os.getenv("EDITH_COMPANION_NAME", "Primary Mac"))
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("Warning: this companion currently implements macOS-specific actions.", file=sys.stderr)

    sio = socketio.Client(reconnection=True, logger=False, engineio_logger=False)

    @sio.event
    def connect():
        sio.emit(
            "companion_register",
            {
                "token": args.token,
                "companion_id": args.companion_id,
                "name": args.name,
                "platform": sys.platform,
                "capabilities": sorted(ACTION_HANDLERS),
                "metadata": {"hostname": os.uname().nodename if hasattr(os, "uname") else ""},
            },
        )
        print(f"Connected Edith companion '{args.companion_id}' to {args.server}")

    @sio.event
    def disconnect():
        print("Edith companion disconnected")

    @sio.on("companion_registered")
    def on_registered(payload):
        print(f"Companion registration confirmed: {payload}")

    @sio.on("companion_action")
    def on_companion_action(payload):
        payload = payload or {}
        action = str(payload.get("action") or "").strip()
        request_id = str(payload.get("id") or "").strip()
        handler = ACTION_HANDLERS.get(action)

        if not request_id:
            return

        try:
            if not handler:
                raise ValueError(f"Unsupported companion action '{action}'.")
            result = handler(dict(payload.get("payload") or {}))
            sio.emit("companion_action_result", {"id": request_id, "success": True, "result": result})
        except Exception as exc:
            sio.emit("companion_action_result", {"id": request_id, "success": False, "error": str(exc)})

    sio.connect(args.server)
    sio.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
