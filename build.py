"""
PersonalAC 学生端客户端打包脚本
运行方式：python build.py [--platform win|mac]
前置要求：pip install pyinstaller>=6.0.0
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f"\n>>> {' '.join(cmd)}\n")
    return subprocess.run(cmd).returncode


def build_windows() -> bool:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--noconsole",
        "--name", "personalac-student",
        "--clean",
        "--add-data", f"common{os.pathsep}common",
        "--add-data", f"student{os.pathsep}student",
        "--hidden-import", "pkgutil",
        "--hidden-import", "importlib.metadata",
        "--hidden-import", "importlib.resources",
    ]
    for mod in ["win32com", "win32gui", "win32process",
                "win32service", "win32serviceutil",
                "win32event", "servicemanager", "pywintypes"]:
        args += ["--hidden-import", mod]
    for mod in ["psutil", "requests",
                "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", "PyQt6.QtSvgWidgets"]:
        args += ["--hidden-import", mod]
    args.append("student.py")

    if run(args) != 0:
        print("[ERROR] Windows build failed")
        return False

    # zip onedir bundle
    src = Path("dist/personalac-student")
    out = Path("dist/personalac-student-win64.zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            zf.write(f, f.relative_to(src.parent))
    print(f"[OK] {out}  ({out.stat().st_size // 1024 // 1024} MB)")
    return True


def build_mac() -> bool:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--windowed",
        "--name", "personalac-student",
        "--clean",
        "--add-data", f"common{os.pathsep}common",
        "--add-data", f"student{os.pathsep}student",
        "--hidden-import", "pkgutil",
        "--hidden-import", "importlib.metadata",
        "--hidden-import", "importlib.resources",
        "--osx-bundle-identifier", "com.personalac.student",
    ]
    for mod in ["psutil", "requests",
                "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", "PyQt6.QtSvgWidgets"]:
        args += ["--hidden-import", mod]
    args.append("student.py")

    if run(args) != 0:
        print("[ERROR] Mac build failed")
        return False

    # create .dmg with Applications symlink
    app = Path("dist/personalac-student.app")
    dmg_staging = Path("dist/dmg-staging")
    if dmg_staging.exists():
        shutil.rmtree(dmg_staging)
    dmg_staging.mkdir()
    shutil.copytree(app, dmg_staging / "PersonalAC.app")
    os.symlink("/Applications", dmg_staging / "Applications")

    out = Path("dist/personalac-student-mac.dmg")
    if out.exists():
        out.unlink()
    rc = run([
        "hdiutil", "create",
        "-volname", "PersonalAC",
        "-srcfolder", str(dmg_staging),
        "-ov", "-format", "UDZO",
        str(out),
    ])
    shutil.rmtree(dmg_staging)
    if rc != 0:
        print("[ERROR] dmg creation failed")
        return False
    print(f"[OK] {out}  ({out.stat().st_size // 1024 // 1024} MB)")
    return True


if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else sys.platform
    print("PersonalAC Student Client — Build")
    print("=" * 40)

    if platform in ("mac", "darwin", "macos"):
        ok = build_mac()
    elif platform in ("win", "win32", "windows"):
        ok = build_windows()
    else:
        # 自动检测
        ok = build_mac() if sys.platform == "darwin" else build_windows()

    sys.exit(0 if ok else 1)
