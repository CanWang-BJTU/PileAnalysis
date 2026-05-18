"""Standalone launcher entry for the integrated PileAnalysis desktop shell."""

import argparse
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

def _runtime_root_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


ROOT_DIR = _runtime_root_dir()
for extra_dir in (ROOT_DIR / "nonlinear_framework", ROOT_DIR / "language_settings"):
    extra_path = str(extra_dir)
    if extra_path not in sys.path:
        sys.path.insert(0, extra_path)

from gui_shell import run_launcher, run_target


def _show_unhandled_exception(exc_type, exc_value, exc_tb):
    message = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        log_path = Path(__file__).resolve().with_name("launcher_error.log")
        log_path.write_text(message, encoding="utf-8")
    except Exception:
        pass
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, "Unhandled Error", message)
        else:
            sys.stderr.write(message)
    except Exception:
        sys.stderr.write(message)


sys.excepthook = _show_unhandled_exception


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--target", choices=["nonlinear", "m-method"])
    args, _unknown = parser.parse_known_args()
    if args.target:
        raise SystemExit(run_target(args.target))
    raise SystemExit(run_launcher())
