import os
import py_compile
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


STAGE7_FILES = [
    "build_common.py",
    "build_win.py",
    "build_linux.py",
    "build_nuitka.py",
    "core/utils/updater.py",
    "core/utils/config.py",
    "main.py",
    "gui/windows/settings_window.py",
]


class TestStage7BuildAndUpdater(unittest.TestCase):
    def test_01_py_compile_all_stage7_files(self):
        for rel_path in STAGE7_FILES:
            abs_path = ROOT_DIR / rel_path
            self.assertTrue(abs_path.is_file(), f"Missing file: {rel_path}")
            py_compile.compile(str(abs_path), doraise=True)

    def test_02_build_commands_win_vs_linux(self):
        import build_common
        import build_linux
        import build_win

        py_linux = build_common.resolve_python("linux", verbose=False)
        self.assertTrue(os.path.isfile(py_linux))
        sp_linux = build_common.get_site_packages_dir(py_linux, "linux")
        self.assertTrue(os.path.isdir(sp_linux))
        ut_linux = build_common.get_unittest_dir(py_linux, "linux")
        self.assertTrue(os.path.isdir(ut_linux))

        linux_cmd = build_linux.build_nuitka_command_linux(py_linux)
        self.assertIn("--output-filename=Akira", linux_cmd)
        self.assertIn("--include-qt-plugins=platforms,multimedia,imageformats,iconengines", linux_cmd)
        self.assertIn("--nofollow-import-to=pycaw", linux_cmd)
        self.assertIn("--nofollow-import-to=comtypes", linux_cmd)
        self.assertTrue(any(arg.startswith("--linux-icon=") for arg in linux_cmd))
        self.assertNotIn("--mingw64", linux_cmd)
        self.assertFalse(any(arg.startswith("--windows-") for arg in linux_cmd))

        win_cmd = build_win.build_nuitka_command_win("C:\\Python\\python.exe")
        self.assertIn("--mingw64", win_cmd)
        self.assertIn("--output-filename=Akira.exe", win_cmd)
        self.assertIn("--windows-console-mode=disable", win_cmd)
        self.assertTrue(any(arg.startswith("--windows-icon-from-ico=") for arg in win_cmd))

    def test_03_copy_resources_excludes_win_installers_and_cleans(self):
        import build_common

        with tempfile.TemporaryDirectory(prefix="akira_s7_res_") as tmp:
            fake_base = Path(tmp) / "repo"
            out_linux = Path(tmp) / "dist_linux"
            out_win = Path(tmp) / "dist_win"

            (fake_base / "assets" / "icon" / "png").mkdir(parents=True)
            (fake_base / "assets" / "installers").mkdir(parents=True)
            (fake_base / "optimized_models" / "piper").mkdir(parents=True)
            (fake_base / "services" / "vpn" / "templates").mkdir(parents=True)
            (fake_base / "core" / "games").mkdir(parents=True)
            (fake_base / "core" / "utils").mkdir(parents=True)
            (fake_base / "personal_data" / "configs").mkdir(parents=True)

            (fake_base / "assets" / "icon" / "png" / "akira_icon.png").write_bytes(b"PNG")
            (fake_base / "assets" / "installers" / "vlc_installer.exe").write_bytes(b"MZ")
            (fake_base / "assets" / "installers" / "torrserver.exe").write_bytes(b"MZ")
            (fake_base / "optimized_models" / "piper" / "voice.onnx").write_bytes(b"ONNX")
            (fake_base / "core" / "utils" / "timezones.json").write_text("{}", encoding="utf-8")
            (fake_base / "personal_data" / "configs" / "config.template.json").write_text("{}", encoding="utf-8")

            build_common.copy_project_resources(
                target_platform="linux",
                output_app_dir=str(out_linux),
                exclude_win_installers=True,
                base_dir=str(fake_base),
            )
            self.assertTrue((out_linux / "assets" / "icon" / "png" / "akira_icon.png").is_file())
            self.assertFalse((out_linux / "assets" / "installers").exists())
            self.assertFalse((out_linux / "assets" / "installers" / "vlc_installer.exe").exists())
            self.assertFalse((out_linux / "assets" / "installers" / "torrserver.exe").exists())
            self.assertTrue((out_linux / "_internal" / "assets").is_symlink())
            self.assertTrue((out_linux / "_internal" / "optimized_models" / "piper" / "voice.onnx").is_file())

            # Windows preserves duplicated copy & installers for MSI
            build_common.copy_project_resources(
                target_platform="win32",
                output_app_dir=str(out_win),
                exclude_win_installers=False,
                base_dir=str(fake_base),
            )
            self.assertTrue((out_win / "assets" / "installers" / "vlc_installer.exe").is_file())
            self.assertTrue((out_win / "_internal" / "assets" / "installers" / "torrserver.exe").is_file())
            self.assertFalse((out_win / "_internal" / "assets").is_symlink())

            # Cleanup removes dev artifacts and stray Windows binaries on Linux
            (out_linux / "pkg" / "tests").mkdir(parents=True)
            (out_linux / "pkg" / "tests" / "test_x.py").write_text("pass", encoding="utf-8")
            (out_linux / "pkg" / "stray.pyd").write_bytes(b"PYD")
            (out_linux / "torch" / "testing").mkdir(parents=True)
            (out_linux / "torch" / "testing" / "keep.py").write_text("pass", encoding="utf-8")
            build_common.clean_distribution("linux", dist_dir=tmp, output_app_dir=str(out_linux))
            self.assertFalse((out_linux / "pkg" / "tests").exists())
            self.assertFalse((out_linux / "pkg" / "stray.pyd").exists())
            self.assertTrue((out_linux / "torch" / "testing" / "keep.py").is_file())

    def test_04_apply_runtime_patches_on_torch_and_unittest(self):
        import build_common

        with tempfile.TemporaryDirectory(prefix="akira_s7_patch_") as tmp:
            app_dir = Path(tmp)
            (app_dir / "torch" / "distributed").mkdir(parents=True)
            (app_dir / "torch" / "nested" / "_internal").mkdir(parents=True)
            (app_dir / "torch" / "optim").mkdir(parents=True)
            (app_dir / "unittest").mkdir(parents=True)

            (app_dir / "torch" / "distributed" / "__init__.py").write_text(
                'if is_available() and not torch._C._c10d_init():\n'
                '    raise RuntimeError("Failed to initialize torch.distributed")\n',
                encoding="utf-8",
            )
            (app_dir / "torch" / "nested" / "_internal" / "nested_tensor.py").write_text(
                "import torch\nclass ViewBufferFromNested(torch.autograd.Function):\n    pass\n",
                encoding="utf-8",
            )
            (app_dir / "torch" / "__init__.py").write_text(
                "set_grad_enabled as set_grad_enabled,\n)\n\nfrom torch import (\n    nn,\n)\n",
                encoding="utf-8",
            )
            (app_dir / "torch" / "optim" / "optimizer.py").write_text("import torch\n", encoding="utf-8")
            (app_dir / "torch" / "_guards.py").write_text("import unittest.mock\n", encoding="utf-8")
            (app_dir / "unittest" / "__init__.py").write_text("# stdlib\n", encoding="utf-8")

            build_common.apply_runtime_patches(str(app_dir))
            self.assertIn("GradBucket", (app_dir / "torch" / "distributed" / "__init__.py").read_text())
            self.assertIn("_AutogradFunction", (app_dir / "torch" / "nested" / "_internal" / "nested_tensor.py").read_text())
            self.assertIn("FileFinder", (app_dir / "torch" / "__init__.py").read_text())
            self.assertIn("import torch.nn.parameter", (app_dir / "torch" / "optim" / "optimizer.py").read_text())
            self.assertIn("class _DummyMockObj:", (app_dir / "torch" / "_guards.py").read_text())
            self.assertIn("from . import mock", (app_dir / "unittest" / "__init__.py").read_text())

    def test_05_desktop_entry_deb_tarball_and_appdir_packaging(self):
        import build_linux

        desktop_file = ROOT_DIR / "packaging" / "linux" / "akira.desktop"
        self.assertTrue(desktop_file.is_file())
        desktop_text = desktop_file.read_text(encoding="utf-8")
        self.assertIn("StartupWMClass=Akira", desktop_text)
        self.assertIn("Exec=/opt/Akira/Akira %U", desktop_text)
        self.assertIn("Icon=akira", desktop_text)

        if shutil.which("desktop-file-validate"):
            res = subprocess.run(["desktop-file-validate", str(desktop_file)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr or res.stdout)

        with tempfile.TemporaryDirectory(prefix="akira_s7_pkg_") as tmp:
            app_dir = Path(tmp) / "app"
            dist_dir = Path(tmp) / "dist"
            (app_dir / "assets" / "icon" / "png").mkdir(parents=True)
            shutil.copy2(ROOT_DIR / "assets" / "icon" / "png" / "akira_icon.png", app_dir / "assets" / "icon" / "png" / "akira_icon.png")
            bin_path = app_dir / "Akira"
            bin_path.write_text("#!/bin/sh\necho akira\n", encoding="utf-8")
            os.chmod(bin_path, 0o755)

            # Build real .deb package and inspect with dpkg-deb
            deb_path = build_linux.build_deb(str(app_dir), str(dist_dir), version_str="5.1.0")
            self.assertIsNotNone(deb_path)
            self.assertTrue(Path(deb_path).is_file())

            info = subprocess.run(["dpkg-deb", "--info", deb_path], capture_output=True, text=True, check=True).stdout
            self.assertIn("Package: akira", info)
            for dep in build_linux.DEBIAN_DEPENDS:
                self.assertIn(dep, info)

            contents = subprocess.run(["dpkg-deb", "--contents", deb_path], capture_output=True, text=True, check=True).stdout
            self.assertIn("/opt/Akira/Akira", contents)
            self.assertIn("/usr/bin/akira -> /opt/Akira/Akira", contents)
            self.assertIn("/usr/share/applications/akira.desktop", contents)
            self.assertIn("/usr/share/icons/hicolor/256x256/apps/akira.png", contents)

            with tempfile.TemporaryDirectory(prefix="akira_s7_deb_extract_") as deb_ext:
                subprocess.run(["dpkg-deb", "-x", deb_path, deb_ext], check=True)
                deb_desktop = Path(deb_ext) / "usr" / "share" / "applications" / "akira.desktop"
                self.assertIn("Icon=/usr/share/icons/hicolor/256x256/apps/akira.png", deb_desktop.read_text(encoding="utf-8"))

            # Build portable .tar.gz
            tar_path = build_linux.build_tarball(str(app_dir), str(dist_dir), version_str="5.1.0")
            self.assertTrue(Path(tar_path).is_file())
            with tarfile.open(tar_path, "r:gz") as tf:
                names = tf.getnames()
            self.assertTrue(any(n.endswith("/Akira/Akira") for n in names))
            self.assertTrue(any(n.endswith("/install.sh") for n in names))
            self.assertTrue(any(n.endswith("/uninstall.sh") for n in names))
            self.assertTrue(any(n.endswith("/akira.desktop") for n in names))

            # Prepare AppDir layout and test AppImage fallback when appimagetool absent
            appdir_root = Path(tmp) / "AppDir"
            build_linux.prepare_appdir(str(app_dir), str(appdir_root))
            self.assertTrue((appdir_root / "AppRun").is_file())
            self.assertTrue(os.access(appdir_root / "AppRun", os.X_OK))
            self.assertTrue((appdir_root / "akira.desktop").is_file())
            self.assertTrue((appdir_root / ".DirIcon").is_file())
            self.assertTrue((appdir_root / "opt" / "Akira" / "Akira").is_file())

            with patch("build_linux.shutil.which", return_value=None):
                self.assertIsNone(build_linux.build_appimage(str(app_dir), str(dist_dir), "5.1.0"))

    def test_06_updater_crossplatform_selection_and_apply(self):
        from core.utils import updater

        assets = [
            {"name": "Akira-Setup-v5.1.0.msi", "browser_download_url": "https://example.com/Akira-Setup-v5.1.0.msi"},
            {"name": "Akira-v5.1.0.exe", "browser_download_url": "https://example.com/Akira-v5.1.0.exe"},
            {"name": "akira_5.1.0_amd64.deb", "browser_download_url": "https://example.com/akira_5.1.0_amd64.deb"},
            {"name": "Akira-x86_64-v5.1.0.AppImage", "browser_download_url": "https://example.com/Akira-x86_64-v5.1.0.AppImage"},
            {"name": "Akira-Linux-x86_64-v5.1.0.tar.gz", "browser_download_url": "https://example.com/Akira-Linux-x86_64-v5.1.0.tar.gz"},
        ]

        url_win, name_win = updater.select_release_asset(assets, target_platform="win32")
        self.assertTrue(name_win.endswith(".msi"))
        self.assertEqual(updater.get_update_filename(url_win, name_win), "Akira_Update.msi")

        url_deb, name_deb = updater.select_release_asset(assets, target_platform="linux", in_appimage=False)
        self.assertTrue(name_deb.endswith(".deb"))
        self.assertEqual(updater.get_update_filename(url_deb, name_deb), "Akira_Update.deb")

        url_app, name_app = updater.select_release_asset(assets, target_platform="linux", in_appimage=True)
        self.assertTrue(name_app.lower().endswith(".appimage"))
        self.assertEqual(updater.get_update_filename(url_app, name_app), "Akira_Update.AppImage")

        # Windows apply_update_and_restart preserves msiexec
        with patch.object(updater.sys, "platform", "win32"), \
                patch("core.utils.updater.subprocess.Popen") as mock_popen, \
                patch("core.utils.updater.sys.exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                updater.apply_update_and_restart("C:\\Temp\\Akira_Update.msi")
            mock_popen.assert_called_once_with(["msiexec.exe", "/i", "C:\\Temp\\Akira_Update.msi"])

        # Linux .deb with pkexec
        with patch.object(updater.sys, "platform", "linux"), \
                patch("core.utils.updater.shutil.which", side_effect=lambda x: f"/usr/bin/{x}" if x in ("pkexec", "apt") else None), \
                patch("core.utils.updater.subprocess.Popen") as mock_popen, \
                patch("core.utils.updater.sys.exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                updater.apply_update_and_restart("/tmp/Akira_Update.deb")
            mock_popen.assert_called_once_with(
                ["/usr/bin/pkexec", "/usr/bin/apt", "install", "-y", "/tmp/Akira_Update.deb"],
                start_new_session=True,
            )

        # Linux .deb fallback to xdg-open when pkexec missing
        with patch.object(updater.sys, "platform", "linux"), \
                patch("core.utils.updater.shutil.which", return_value=None), \
                patch("core.utils.updater.subprocess.Popen") as mock_popen, \
                patch("core.utils.updater.sys.exit", side_effect=SystemExit(0)):
            with self.assertRaises(SystemExit):
                updater.apply_update_and_restart("/tmp/Akira_Update.deb")
            mock_popen.assert_called_once_with(
                ["xdg-open", "/tmp/Akira_Update.deb"],
                start_new_session=True,
            )

        # Linux AppImage self-replace and relaunch
        with tempfile.TemporaryDirectory(prefix="akira_s7_upd_") as tmp:
            old_ai = Path(tmp) / "Akira.AppImage"
            new_ai = Path(tmp) / "Akira_Update.AppImage"
            old_ai.write_bytes(b"OLD_IMAGE")
            new_ai.write_bytes(b"NEW_IMAGE")
            with patch.object(updater.sys, "platform", "linux"), \
                    patch.dict(os.environ, {"APPIMAGE": str(old_ai)}, clear=False), \
                    patch("core.utils.updater.subprocess.Popen") as mock_popen, \
                    patch("core.utils.updater.sys.exit", side_effect=SystemExit(0)):
                with self.assertRaises(SystemExit):
                    updater.apply_update_and_restart(str(new_ai))
                self.assertEqual(old_ai.read_bytes(), b"NEW_IMAGE")
                self.assertTrue(os.access(old_ai, os.X_OK))
                mock_popen.assert_called_once_with([str(old_ai)], start_new_session=True)

    def test_07_frozen_symlink_resource_path_resolution(self):
        from core.utils import config as cfg_mod

        with tempfile.TemporaryDirectory(prefix="akira_s7_sym_") as tmp:
            real_dir = Path(tmp) / "opt" / "Akira"
            bin_dir = Path(tmp) / "usr" / "bin"
            (real_dir / "assets").mkdir(parents=True)
            bin_dir.mkdir(parents=True)
            real_bin = real_dir / "Akira"
            real_bin.write_text("", encoding="utf-8")
            (real_dir / "assets" / "marker.txt").write_text("ok", encoding="utf-8")
            link_bin = bin_dir / "akira"
            os.symlink(real_bin, link_bin)

            with patch.object(cfg_mod.sys, "frozen", True, create=True), \
                    patch.object(cfg_mod.sys, "executable", str(link_bin)):
                resolved = cfg_mod.get_resource_path("assets", "marker.txt")
                self.assertEqual(Path(resolved), real_dir / "assets" / "marker.txt")
                self.assertTrue(Path(resolved).is_file())


if __name__ == "__main__":
    unittest.main()
