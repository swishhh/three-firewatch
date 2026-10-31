"""CPU and GPU utilization samplers for the stats overlay."""
import ctypes
import glob
import os
import time


class CpuUsage:
    """Whole-machine CPU % (from /proc/stat) and this process's usage as % of one core."""

    def __init__(self):
        self._system = self._read_system()
        self._process = self._read_process()

    @staticmethod
    def _read_system():
        try:
            with open('/proc/stat') as file:
                values = [int(value) for value in file.readline().split()[1:]]
        except OSError:
            return None
        return sum(values), values[3] + values[4]  # total, idle + iowait

    @staticmethod
    def _read_process():
        times = os.times()
        return times.user + times.system, time.perf_counter()

    def sample(self):
        """(system %, process % of one core) since the previous call."""
        system, process = self._read_system(), self._read_process()

        process_percent = 100 * (process[0] - self._process[0]) / max(process[1] - self._process[1], 1e-6)
        if system and self._system and system[0] > self._system[0]:
            total, idle = system[0] - self._system[0], system[1] - self._system[1]
            system_percent = 100 * (total - idle) / total
        else:
            system_percent = process_percent / (os.cpu_count() or 1)

        self._system, self._process = system, process
        return system_percent, process_percent


class _NvmlUtilization(ctypes.Structure):
    _fields_ = [('gpu', ctypes.c_uint), ('memory', ctypes.c_uint)]


class GpuUsage:
    """Whole-GPU busy % from NVIDIA's NVML, or amdgpu's sysfs counter. `sample()` is None without either."""

    def __init__(self):
        self._nvml = None
        self._handle = ctypes.c_void_p()
        self._sysfs = None

        for library in ('libnvidia-ml.so.1', 'nvml.dll'):
            try:
                nvml = ctypes.CDLL(library)
            except OSError:
                continue
            if nvml.nvmlInit_v2() == 0 and nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self._handle)) == 0:
                self._nvml = nvml
            break

        if self._nvml is None:
            paths = sorted(glob.glob('/sys/class/drm/card*/device/gpu_busy_percent'))
            self._sysfs = paths[0] if paths else None

    def sample(self):
        if self._nvml is not None:
            utilization = _NvmlUtilization()
            if self._nvml.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(utilization)) == 0:
                return float(utilization.gpu)
        elif self._sysfs is not None:
            try:
                with open(self._sysfs) as file:
                    return float(file.read())
            except (OSError, ValueError):
                pass
        return None
