"""Entry point for the Hardlink Manager application."""

import sys

from hardlink_manager.ui.app import HardlinkManagerApp


def main():
    app = HardlinkManagerApp()
    app.run()


if __name__ == "__main__":
    main()
