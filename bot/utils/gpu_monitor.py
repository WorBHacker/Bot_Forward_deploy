import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GpuInfo:
    index: int
    name: str
    temperature_c: int
    memory_used_mb: int
    memory_total_mb: int
    utilization_pct: int


async def get_gpu_status() -> Optional[List[GpuInfo]]:
    """
    Return GPU stats via pynvml.  Returns None if NVML is unavailable
    (e.g. no NVIDIA driver or running on CPU-only host).
    Runs in a thread pool so it doesn't block the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _collect_gpu_info)


def _collect_gpu_info() -> Optional[List[GpuInfo]]:
    try:
        import pynvml  # type: ignore

        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        results: List[GpuInfo] = []

        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            results.append(
                GpuInfo(
                    index=i,
                    name=name,
                    temperature_c=temp,
                    memory_used_mb=mem.used // (1024 * 1024),
                    memory_total_mb=mem.total // (1024 * 1024),
                    utilization_pct=util.gpu,
                )
            )
        return results
    except Exception as exc:
        logger.debug("pynvml unavailable: %s", exc)
        return None


def format_gpu_status(gpus: Optional[List[GpuInfo]]) -> str:
    if not gpus:
        return "⚠️ GPU информация недоступна (нет NVML или NVIDIA GPU)."

    lines = ["🖥 <b>GPU Status</b>\n"]
    for g in gpus:
        lines.append(
            f"<b>[GPU {g.index}] {g.name}</b>\n"
            f"  🌡 Температура: {g.temperature_c}°C\n"
            f"  💾 VRAM: {g.memory_used_mb} / {g.memory_total_mb} MB "
            f"({g.memory_used_mb * 100 // max(g.memory_total_mb, 1)}%)\n"
            f"  ⚡ Загрузка GPU: {g.utilization_pct}%"
        )
    return "\n".join(lines)
