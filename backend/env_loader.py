from pathlib import Path

from dotenv import load_dotenv


def load_edith_env():
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent

    tracked_env = project_root / ".env.railway"
    if tracked_env.exists():
        load_dotenv(tracked_env, override=False)

    default_env = project_root / ".env"
    if default_env.exists():
        load_dotenv(default_env, override=False)
