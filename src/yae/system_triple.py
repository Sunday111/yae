from __future__ import annotations

import platform


# Normalizes the host OS and CPU into the key a binary dependency selects an
# artifact by. Kept deliberately coarse - os-arch - because that is the axis a
# prebuilt release actually varies on; finer distinctions a release bakes into a
# single artifact (a glibc baseline, for one) belong in the manifest's URL, not
# here. Determined from the running system, never hardcoded, so the same manifest
# resolves to the right download on every machine.

_OS_NAMES = {
    "linux": "linux",
    "darwin": "macos",
    "windows": "windows",
}

_ARCH_NAMES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def current_system_triple() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = _OS_NAMES.get(system, system)
    arch_name = _ARCH_NAMES.get(machine, machine)
    return f"{os_name}-{arch_name}"
