"""Entry point for the Hardlink Manager application."""

import io
import sys
import tkinter as tk
from tkinter import messagebox


def _fix_noconsole_streams():
    """Redirect stdio to devnull when running as a --noconsole exe.

    PyInstaller's --noconsole sets sys.stderr/stdout to None, which crashes
    tkinter's default exception reporter (it tries to write to stderr).
    """
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    if sys.stdout is None:
        sys.stdout = io.StringIO()


def _install_exception_handler(root: tk.Tk):
    """Show unhandled exceptions in a messagebox instead of crashing."""
    def handle_exception(exc_type, exc_value, exc_tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            messagebox.showerror("Unexpected Error", msg)
        except Exception:
            pass
    root.report_callback_exception = handle_exception


def main():
    _fix_noconsole_streams()

    from hardlink_manager.ui.app import HardlinkManagerApp
    app = HardlinkManagerApp()
    _install_exception_handler(app.root)
    app.run()


if __name__ == "__main__":
    main()
