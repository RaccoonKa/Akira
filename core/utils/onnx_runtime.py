"""Общая настройка и создание GPU/CPU ONNX Runtime сессий для моделей Акиры."""

import os
import sys

_GPU_DLLS_PREPARED = False


def _has_nvidia_cuda_runtime() -> bool:
    """Проверяет наличие CUDA/NVIDIA окружения на Linux до вызова ort.preload_dlls()."""
    if sys.platform == "win32":
        return True
    if os.path.exists("/dev/nvidia0") or os.path.exists("/proc/driver/nvidia/version"):
        return True
    for env_key in ("CUDA_PATH", "CUDA_HOME"):
        if os.environ.get(env_key):
            return True
    return False


def prepare_onnx_gpu_env(ort_module=None):
    """Подгружает CUDA/cuDNN библиотеки из venv или сборки перед инициализацией GPU-провайдера."""
    global _GPU_DLLS_PREPARED
    if _GPU_DLLS_PREPARED:
        return
    _GPU_DLLS_PREPARED = True

    if ort_module is None:
        try:
            import onnxruntime as ort_module
        except Exception:
            return

    try:
        if hasattr(ort_module, "set_default_logger_severity"):
            ort_module.set_default_logger_severity(3)
    except Exception:
        pass

    if not _has_nvidia_cuda_runtime():
        return

    try:
        preload_fn = getattr(ort_module, "preload_dlls", None)
        if callable(preload_fn):
            preload_fn(cuda=True, cudnn=True)
    except Exception:
        pass


def get_onnx_execution_providers(ort_module=None, platform: str | None = None) -> list[str]:
    """Возвращает приоритетный список провайдеров ONNX Runtime (GPU -> CPU)."""
    if ort_module is None:
        import onnxruntime as ort_module

    prepare_onnx_gpu_env(ort_module)
    available = list(ort_module.get_available_providers() or [])
    plat = platform or sys.platform

    if plat == "win32":
        for gpu_ep in ("DmlExecutionProvider", "CUDAExecutionProvider"):
            if gpu_ep in available:
                return [gpu_ep, "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    for gpu_ep in ("CUDAExecutionProvider", "ROCMExecutionProvider"):
        if gpu_ep in available:
            return [gpu_ep, "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def describe_execution_provider(provider_name: str) -> str:
    if provider_name == "DmlExecutionProvider":
        return "DirectML"
    return provider_name.replace("ExecutionProvider", "")


def create_onnx_session(
    model_path: str,
    sess_options=None,
    ort_module=None,
    prefer_gpu: bool = True,
):
    """
    Создаёт ort.InferenceSession с автоматическим приоритетом GPU (CUDA/DirectML/ROCm)
    и безопасным откатом на CPUExecutionProvider при отсутствии GPU или неподдерживаемой операции.
    """
    if ort_module is None:
        import onnxruntime as ort_module

    if sess_options is None:
        sess_options = ort_module.SessionOptions()
        sess_options.graph_optimization_level = ort_module.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        sess_options.log_severity_level = 3
    except Exception:
        pass

    providers = get_onnx_execution_providers(ort_module) if prefer_gpu else ["CPUExecutionProvider"]
    if providers[0] != "CPUExecutionProvider":
        try:
            sess = ort_module.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=providers,
            )
            active = list(sess.get_providers() or [])
            if active and active[0] != "CPUExecutionProvider":
                return sess, active[0]
        except Exception:
            pass

    cpu_sess = ort_module.InferenceSession(
        str(model_path),
        sess_options=sess_options,
        providers=["CPUExecutionProvider"],
    )
    return cpu_sess, "CPUExecutionProvider"
