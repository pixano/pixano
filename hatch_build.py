import os
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if version == "editable":
            return

        ui_dir = os.path.join(self.root, "ui")
        app_dir = os.path.join(ui_dir, "apps", "pixano")

        if not os.path.isdir(ui_dir):
            return

        self.app.display_info("Installing frontend dependencies...")
        subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"],
            cwd=ui_dir,
            check=True,
        )

        self.app.display_info("Building frontend...")
        subprocess.run(
            ["pnpm", "build"],
            cwd=app_dir,
            check=True,
        )
