"""
PersonalAC 学生端客户端打包脚本
运行方式：python build.py [win|mac]
前置要求：pip install pyinstaller>=6.0.0
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION = "1.5.1"

# 所有平台通用的 hidden imports
_COMMON_HIDDEN = [
    "pkgutil", "importlib.metadata", "importlib.resources",
    "psutil", "requests", "requests.adapters", "requests.auth",
    "charset_normalizer",
    "PyQt6.QtSvgWidgets",
]

# 排除明确用不到的大型模块，减小包体积
_EXCLUDES = [
    "matplotlib", "numpy", "pandas", "scipy", "PIL", "Pillow",
    "cv2", "sklearn", "tensorflow", "torch",
    "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore",  # 我们不用内嵌浏览器
    "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning",
    "PyQt6.QtSensors", "PyQt6.QtSerialPort",
    "unittest", "test", "doctest",
]


def run(cmd: list[str], cwd: str | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}\n")
    return subprocess.run(cmd, cwd=cwd).returncode


def _base_args(name: str = "personalac-student") -> list[str]:
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", name,
        "--clean",
        "--noconfirm",
        "--add-data", f"common{os.pathsep}common",
        "--add-data", f"student{os.pathsep}student",
        "--collect-submodules", "common",
        "--collect-submodules", "student",
    ]
    for m in _COMMON_HIDDEN:
        args += ["--hidden-import", m]
    for m in _EXCLUDES:
        args += ["--exclude-module", m]
    return args


def build_windows() -> bool:
    args = _base_args()
    args += ["--onedir", "--noconsole"]

    # Windows 专用
    win_hidden = [
        "win32com", "win32gui", "win32process",
        "win32api", "win32con", "pywintypes",
        "win32security", "win32event",
    ]
    for m in win_hidden:
        args += ["--hidden-import", m]

    # 版本信息文件
    version_file = Path("build/version_info.txt")
    version_file.parent.mkdir(exist_ok=True)
    _v = VERSION.replace(".", ", ")
    version_file.write_text(f"""
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({_v}, 0), prodvers=({_v}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'PersonalAC'),
      StringStruct('FileDescription', 'PersonalAC 学生端'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductName', 'PersonalAC Student'),
      StringStruct('ProductVersion', '{VERSION}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
""".strip())
    args += ["--version-file", str(version_file)]
    args.append("student.py")

    if run(args) != 0:
        print("[ERROR] Windows build failed")
        return False

    _strip_pycache(Path("dist/personalac-student"))

    src = Path("dist/personalac-student")
    out = Path(f"dist/personalac-student-win64-{VERSION}.zip")
    out.unlink(missing_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src.parent))

    mb = out.stat().st_size / 1024 / 1024
    print(f"[OK] {out}  ({mb:.1f} MB)")

    # 同时输出一个无版本号的副本供服务器下载路由使用
    plain = Path("dist/personalac-student-win64.zip")
    shutil.copy2(out, plain)
    return True


def build_mac() -> bool:
    args = _base_args()
    args += [
        "--onedir", "--windowed",
        "--osx-bundle-identifier", "com.personalac.student",
    ]
    args.append("student.py")

    if run(args) != 0:
        print("[ERROR] Mac build failed")
        return False

    app = Path("dist/personalac-student.app")
    staging = Path("dist/dmg-staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    shutil.copytree(app, staging / "PersonalAC.app")
    os.symlink("/Applications", staging / "Applications")

    out = Path(f"dist/personalac-student-mac-{VERSION}.dmg")
    out.unlink(missing_ok=True)
    rc = run(["hdiutil", "create", "-volname", "PersonalAC",
              "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(out)])
    shutil.rmtree(staging)
    if rc != 0:
        print("[ERROR] dmg creation failed"); return False

    mb = out.stat().st_size / 1024 / 1024
    print(f"[OK] {out}  ({mb:.1f} MB)")
    shutil.copy2(out, "dist/personalac-student-mac.dmg")
    return True


def _strip_pycache(root: Path):
    """删除打包目录里的 __pycache__ 减小体积"""
    for d in root.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    for f in root.rglob("*.pyc"):
        f.unlink(missing_ok=True)


if __name__ == "__main__":
    plat = sys.argv[1] if len(sys.argv) > 1 else sys.platform
    print(f"PersonalAC Student Client — Build v{VERSION}")
    print("=" * 48)

    if plat in ("mac", "darwin", "macos"):
        ok = build_mac()
    elif plat in ("win", "win32", "windows"):
        ok = build_windows()
    else:
        ok = build_mac() if sys.platform == "darwin" else build_windows()

    sys.exit(0 if ok else 1)
