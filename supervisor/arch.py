"""Handle Arch for underlay maschine/platforms."""

import logging
from pathlib import Path
import platform

from .coresys import CoreSys, CoreSysAttributes
from .exceptions import ConfigurationFileError, HassioArchNotFound
from .utils.json import read_json_file

_LOGGER: logging.Logger = logging.getLogger(__name__)

ARCH_JSON: Path = Path(__file__).parent.joinpath("data/arch.json")

MAP_CPU = {
    "armv7": "armv7",
    "armv6": "armhf",
    "armv8": "aarch64",
    "aarch64": "aarch64",
    "i686": "i386",
    "x86_64": "amd64",
}


class CpuArch(CoreSysAttributes):
    """Manage available architectures."""

    def __init__(self, coresys: CoreSys) -> None:
        """Initialize CPU Architecture handler."""
        self.coresys = coresys
        self._supported_arch: list[str] = []
        self._supported_set: set[str] = set()
        self._default_arch: str

    @property
    def default(self) -> str:
        """Return system default arch."""
        return self._default_arch

    @property
    def supervisor(self) -> str:
        """Return supervisor arch."""
        return self.sys_supervisor.arch

    @property
    def supported(self) -> list[str]:
        """Return support arch by CPU/Machine."""
        return self._supported_arch

    async def load(self) -> None:
        """Load data and initialize default arch."""
        try:
            arch_data = await self.sys_run_in_executor(read_json_file, ARCH_JSON)
        except ConfigurationFileError:
            _LOGGER.warning("Can't read arch json file from %s", ARCH_JSON)
            return

        native_support = self.detect_cpu()
        _LOGGER.info("Native architecture support: %s", native_support)

        # Evaluate current CPU/Platform
        if not self.sys_machine:
            _LOGGER.warning("Can't detect the machine type!")
            self._default_arch = native_support
            self._supported_arch.append(self.default)
            self._supported_set = set(self._supported_arch)
            return
        
        # Special handling for aarch64
        if native_support == "aarch64" or self.sys_machine == "aarch64":
            _LOGGER.info("Setting up aarch64 architecture support")
            self._default_arch = "aarch64"
            # Add architectures that aarch64 can typically support
            self._supported_arch = ["aarch64", "armv7", "armhf"]
            self._supported_set = set(self._supported_arch)
            return
        
        # Normal flow for architectures in arch.json
        if self.sys_machine in arch_data:
            self._supported_arch.extend(arch_data[self.sys_machine])
            self._default_arch = self.supported[0]
        else:
            _LOGGER.warning("Machine type %s not found in arch data!", self.sys_machine)
            self._default_arch = native_support
            self._supported_arch.append(self.default)

        # Make sure native support is in supported list
        if native_support not in self._supported_arch:
            self._supported_arch.append(native_support)

        self._supported_set = set(self._supported_arch)

    def is_supported(self, arch_list: list[str]) -> bool:
        """Return True if there is a supported arch by this platform."""
        return not self._supported_set.isdisjoint(arch_list)

    def match(self, arch_list: list[str]) -> str:
        """Return best match for this CPU/Platform."""
        for self_arch in self.supported:
            if self_arch in arch_list:
                return self_arch
        raise HassioArchNotFound()

    def detect_cpu(self) -> str:
        """Return the arch type of local CPU."""
        # Get CPU arch
        cpu_arch = platform.machine().lower()
        
        # Make sure we map correctly
        if cpu_arch in MAP_CPU:
            return MAP_CPU[cpu_arch]
        
        # Handle specific cases
        if "aarch64" in cpu_arch:
            return "aarch64"
        if "arm" in cpu_arch and "v8" in cpu_arch:
            return "aarch64"
        if "arm" in cpu_arch and "v7" in cpu_arch:
            return "armv7"
        if "arm" in cpu_arch:
            return "armhf"
        
        _LOGGER.warning("Unsupported CPU architecture: %s", cpu_arch)
        return "amd64"  # Default to amd64 if unknown
