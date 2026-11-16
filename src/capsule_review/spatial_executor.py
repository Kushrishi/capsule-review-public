"""Linux read-only input mounts and a private writable output for CR-SP-01."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import site
import stat


def isolation_command(command, read_paths, output, forbidden_paths, *, devices=()):
    executable = shutil.which("bwrap")
    output = Path(output).resolve()
    roots = [Path(p).resolve() for p in read_paths]
    system = [Path(p) for p in ("/usr", "/lib", "/lib64", "/opt", "/etc") if Path(p).exists()]
    user_packages = Path(site.getusersitepackages()).resolve()
    if user_packages.exists():
        system.append(user_packages)
    if not forbidden_paths:
        raise ValueError("Explicit external evaluation paths are required")
    for forbidden in map(lambda p: Path(p).resolve(), forbidden_paths):
        if any(forbidden.is_relative_to(p) for p in [output, *roots, *system]):
            raise ValueError("An input/output mount exposes external evaluation")
    if any(p == Path("/") or p == Path("/workspace") for p in roots):
        raise ValueError("Broad workspace mounts are prohibited")
    gpu_nodes = []
    for device in devices:
        path = Path(device).resolve()
        allowed_name = ((path.parent == Path("/dev") and path.name.startswith("nvidia")) or
                        path.parent == Path("/dev/nvidia-caps"))
        if not allowed_name or not stat.S_ISCHR(path.stat().st_mode):
            raise ValueError("Only NVIDIA character devices may be mounted")
        gpu_nodes.append(path)
    if not executable:
        raise RuntimeError("bubblewrap is required for executor isolation")
    args = [executable, "--die-with-parent", "--new-session",
            "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for path in [*system, *roots]:
        args += ["--ro-bind", str(path), str(path)]
    for path in gpu_nodes:
        args += ["--dev-bind", str(path), str(path)]
    args += ["--bind", str(output), str(output), "--chdir", str(output), "--"]
    return args + list(command)


def execute_isolated(command, read_paths, output, forbidden_paths, *, timeout=60, devices=()):
    """Fail closed on namespace/mount errors. External paths are never mounted."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    args = isolation_command(command, read_paths, output, forbidden_paths, devices=devices)
    dependency_roots = (Path("/opt"), Path("/usr"),
                        Path(site.getusersitepackages()).resolve())
    runtime_paths = []
    for entry in sys.path:
        if entry and any(Path(entry).resolve().is_relative_to(root) for root in dependency_roots):
            runtime_paths.append(str(Path(entry).resolve()))
    environment = {"PATH": os.defpath, "PYTHONNOUSERSITE": "1",
                   "PYTHONPATH": os.pathsep.join(runtime_paths),
                   "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
    return subprocess.run(args, close_fds=True, capture_output=True, text=True,
                          timeout=timeout, env=environment, check=True)
