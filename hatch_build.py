# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Custom build hook to build the frontend during package build."""

    def initialize(self, version, build_data):
        """Build frontend assets using pnpm, skipped for editable installs."""
        if version == "editable":
            return

        ui_dir = os.path.join(self.root, "ui")
        legacy_app_dir = os.path.join(ui_dir, "apps", "pixano")
        web_app_dir = os.path.join(ui_dir, "apps", "web")

        if not os.path.isdir(ui_dir):
            return

        self.app.display_info("Installing frontend dependencies...")
        subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"],
            cwd=ui_dir,
            check=True,
        )

        self.app.display_info("Building legacy frontend...")
        subprocess.run(
            ["pnpm", "build"],
            cwd=legacy_app_dir,
            check=True,
        )

        self.app.display_info("Building web frontend...")
        subprocess.run(
            ["pnpm", "build"],
            cwd=web_app_dir,
            check=True,
        )
