"""Vendor-agnostic GPU acceleration abstraction layer.

Supports NVIDIA CUDA, Intel OpenCL, and ARM Vulkan through a unified interface.
Automatically detects available hardware and selects optimal backend.
"""

import os
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
import numpy as np


@dataclass
class GPUInfo:
    """Information about detected GPU."""
    
    device_id: int
    vendor: str  # "nvidia" | "intel" | "arm" | "unknown"
    name: str
    memory_gb: float
    compute_capability: Tuple[int, int]
    is_available: bool


@dataclass
class GPUContext:
    """GPU context for a specific device."""
    
    device_id: int
    vendor: str
    backend_name: str  # "cuda" | "opencl" | "vulkan"
    initialized: bool = False
    
    def get_device_string(self) -> str:
        """Returns the device string for the current backend."""
        if self.vendor == "nvidia":
            return f"cuda:{self.device_id}"
        elif self.vendor == "intel":
            return f"opencl:{self.device_id}"
        else:
            return f"{self.backend_name}:{self.device_id}"


class GPUBackend:
    """Abstract base class for GPU backends."""
    
    @property
    def name(self) -> str:
        raise NotImplementedError
    
    @property
    def supports_float16(self) -> bool:
        raise NotImplementedError
    
    @property
    def supports_int8_quantization(self) -> bool:
        raise NotImplementedError
    
    def set_device(self, device_id: int) -> None:
        raise NotImplementedError
    
    def get_device_count(self) -> int:
        raise NotImplementedError
    
    def allocate_tensor(self, shape: Tuple[int, ...], dtype=np.float32) -> Any:
        """Allocate GPU tensor."""
        raise NotImplementedError
    
    def copy_to_gpu(self, data: np.ndarray) -> Any:
        """Copy numpy array to GPU."""
        raise NotImplementedError
    
    def copy_from_gpu(self, gpu_tensor: Any) -> np.ndarray:
        """Copy GPU tensor to numpy array."""
        raise NotImplementedError
    
    def synchronize(self) -> None:
        """Synchronize with host memory."""
        pass


class CUDABackend(GPUBackend):
    """NVIDIA CUDA backend implementation."""
    
    name = "cuda"
    supports_float16 = True
    supports_int8_quantization = True
    
    def __init__(self, device_id: int = 0):
        import torch
        
        self._device = f"cuda:{device_id}"
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available")
        
        # Verify the specific GPU is available
        if not torch.cuda.device_available(device_id):
            raise RuntimeError(f"CUDA device {device_id} is not available")
    
    @property
    def compute_capability(self) -> Tuple[int, int]:
        import torch
        return (torch.cuda.get_device_capability()[0], 
                torch.cuda.get_device_capability()[1])
    
    def set_device(self, device_id: int) -> None:
        self._device = f"cuda:{device_id}"
    
    def get_device_count(self) -> int:
        import torch
        return torch.cuda.device_count()
    
    def allocate_tensor(self, shape: Tuple[int, ...], dtype=np.float32) -> Any:
        import torch
        return torch.empty(shape, dtype=torch.from_numpy(dtype).torch_dtype())\
            .to(self._device)
    
    def copy_to_gpu(self, data: np.ndarray) -> Any:
        import torch
        return torch.tensor(data, device=self._device)
    
    def copy_from_gpu(self, gpu_tensor: Any) -> np.ndarray:
        import torch
        return gpu_tensor.cpu().numpy()
    
    def synchronize(self) -> None:
        import torch
        torch.cuda.synchronize(self._device)


class OpenCLBackend(GPUBackend):
    """Intel OpenCL backend implementation."""
    
    name = "opencl"
    supports_float16 = False  # Limited support
    supports_int8_quantization = True
    
    def __init__(self, device_id: int = 0):
        try:
            import pyopencl as cl
        except ImportError:
            raise RuntimeError("pyopencl is not installed")
        
        self._context = None
        self._queue = None
        
        # Find OpenCL devices
        platforms = cl.get_platforms()
        if not platforms:
            raise RuntimeError("No OpenCL platforms found")
        
        # Prefer Intel GPUs
        intel_found = False
        for platform in platforms:
            devices = list(platform.get_devices(cl.device_type.CL_DEVICE_TYPE_GPU))
            for device in devices:
                if "Intel" in device.name or "AMD" in device.name:
                    self._context = cl.Context([device])
                    self._queue = cl.CommandQueue(self._context)
                    intel_found = True
                    break
            if intel_found:
                break
        
        # Fallback to any GPU
        if not intel_found and platforms:
            devices = list(platforms[0].get_devices(cl.device_type.CL_DEVICE_TYPE_GPU))
            self._context = cl.Context(devices)
            self._queue = cl.CommandQueue(self._context)
    
    @property
    def compute_capability(self) -> Tuple[int, int]:
        # OpenCL doesn't have the same concept as CUDA
        return (10, 0)  # Default to compute capability 1.0
    
    def set_device(self, device_id: int) -> None:
        # OpenCL uses context/queue instead of device selection
        pass
    
    def get_device_count(self) -> int:
        if self._context is not None:
            return len(list(self._context.get_info(cl.Context.INFO_NUM_DEVICES)))
        return 0
    
    def allocate_tensor(self, shape: Tuple[int, ...], dtype=np.float32) -> Any:
        import pyopencl as cl
        
        # Create buffer
        mem = cl.Buffer(
            self._context, 
            cl.mem_flags.READ_WRITE, 
            np.prod(shape) * np.dtype(dtype).itemsize
        )
        
        return (mem, shape, dtype)
    
    def copy_to_gpu(self, data: np.ndarray) -> Any:
        import pyopencl as cl
        
        mem = cl.Buffer(
            self._context, 
            cl.mem_flags.READ_WRITE, 
            data.nbytes
        )
        
        self._queue.enqueue_write_buffer(mem, np.array(data))
        
        return (mem, data.shape, data.dtype)
    
    def copy_from_gpu(self, gpu_tensor: Any) -> np.ndarray:
        import pyopencl as cl
        
        mem, shape, dtype = gpu_tensor
        result = np.empty(shape, dtype=dtype)
        
        self._queue.enqueue_read_buffer(mem, np.array(result))
        
        return result
    
    def synchronize(self) -> None:
        if self._queue is not None:
            self._queue.finish()


class VulkanBackend(GPUBackend):
    """ARM Vulkan backend implementation."""
    
    name = "vulkan"
    supports_float16 = True  # Limited support
    supports_int8_quantization = False
    
    def __init__(self, device_id: int = 0):
        try:
            import pyvulkan as vulkan
        except ImportError:
            raise RuntimeError("pyvulkan is not installed")
        
        self._instance = None
        self._physical_device = None
        self._device = None
    
    @property
    def compute_capability(self) -> Tuple[int, int]:
        # Vulkan doesn't have the same concept as CUDA
        return (10, 0)  # Default to compute capability 1.0
    
    def set_device(self, device_id: int) -> None:
        pass
    
    def get_device_count(self) -> int:
        if self._instance is not None and self._physical_device is not None:
            return self._physical_device.get_properties().deviceCount
        return 0
    
    def allocate_tensor(self, shape: Tuple[int, ...], dtype=np.float32) -> Any:
        # Vulkan tensor allocation requires a more complex setup
        # This is a simplified placeholder
        raise NotImplementedError("Vulkan tensor allocation not fully implemented")
    
    def copy_to_gpu(self, data: np.ndarray) -> Any:
        raise NotImplementedError("Vulkan memory transfer not fully implemented")
    
    def copy_from_gpu(self, gpu_tensor: Any) -> np.ndarray:
        raise NotImplementedError("Vulkan memory transfer not fully implemented")
    
    def synchronize(self) -> None:
        pass


class GPUSelector:
    """Automatically selects the best available GPU backend."""
    
    _backends = {
        "nvidia": CUDABackend,
        "intel": OpenCLBackend,
        "arm": VulkanBackend,
    }
    
    @classmethod
    def detect_available_gpus(cls) -> List[GPUInfo]:
        """Detect all available GPUs and their capabilities."""
        gpus = []
        
        # Check for NVIDIA CUDA
        try:
            import torch
            
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                
                for i in range(device_count):
                    name = torch.cuda.get_device_name(i)
                    memory = torch.cuda.mem_get_info(i)[1] / (1024**3)  # GB
                    
                    gpus.append(GPUInfo(
                        device_id=i,
                        vendor="nvidia",
                        name=name,
                        memory_gb=memory,
                        compute_capability=torch.cuda.get_device_capability(i),
                        is_available=True
                    ))
        except Exception:
            pass
        
        # Check for OpenCL (Intel/AMD)
        try:
            import pyopencl as cl
            
            platforms = cl.get_platforms()
            
            for platform in platforms:
                devices = list(platform.get_devices(cl.device_type.CL_DEVICE_TYPE_GPU))
                
                for device in devices:
                    name = device.name
                    
                    # Skip if already detected as NVIDIA
                    if any(gpu.vendor == "nvidia" and gpu.name == name for gpu in gpus):
                        continue
                    
                    memory = device.get_info(cl.device_type.CL_DEVICE_GLOBAL_MEM_SIZE) / (1024**3)
                    
                    gpus.append(GPUInfo(
                        device_id=0,  # OpenCL doesn't expose device ID easily
                        vendor="intel" if "Intel" in name or "AMD" in name else "unknown",
                        name=name,
                        memory_gb=memory,
                        compute_capability=(10, 0),
                        is_available=True
                    ))
        except Exception:
            pass
        
        # Check for Vulkan (ARM)
        try:
            import pyvulkan as vulkan
            
            instance = vulkan.Instance()
            physical_devices = instance.enumerate_physical_devices()
            
            for device in physical_devices:
                name = device.get_properties().deviceName
                
                # Skip if already detected
                if any(gpu.name == name for gpu in gpus):
                    continue
                
                memory = device.get_memory_properties(0).memoryHeapInfo[0].size / (1024**3)
                
                gpus.append(GPUInfo(
                    device_id=0,  # Vulkan doesn't expose device ID easily
                    vendor="arm" if "ARM" in name else "unknown",
                    name=name,
                    memory_gb=memory,
                    compute_capability=(10, 0),
                    is_available=True
                ))
        except Exception:
            pass
        
        return gpus
    
    @classmethod
    def select_best_backend(cls) -> Tuple[str, GPUBackend]:
        """Select the best available GPU backend."""
        gpus = cls.detect_available_gpus()
        
        if not gpus:
            raise RuntimeError("No GPUs detected. Running on CPU only.")
        
        # Priority: NVIDIA > Intel/AMD > ARM
        priority = {"nvidia": 0, "intel": 1, "arm": 2}
        
        best_gpu = max(gpus, key=lambda g: (priority.get(g.vendor, 3), -g.memory_gb))
        
        if not best_gpu.is_available:
            raise RuntimeError(f"Best GPU {best_gpu.name} is not available")
        
        backend_class = cls._backends.get(best_gpu.vendor)
        if backend_class is None:
            raise RuntimeError(f"No backend available for vendor: {best_gpu.vendor}")
        
        return best_gpu.vendor, backend_class(best_gpu.device_id)
    
    @classmethod
    def get_vendor_agnostic_device_string(cls, backend: GPUBackend) -> str:
        """Returns a device string that works across vendors."""
        if hasattr(backend, 'get_device_string'):
            return backend.get_device_string()
        
        # Fallback for CPU-only mode
        return "cpu"


# Global GPU context (lazy initialization)
_gpu_context: Optional[Tuple[str, GPUBackend]] = None


def get_gpu_backend() -> GPUBackend:
    """Get the current GPU backend instance."""
    global _gpu_context
    
    if _gpu_context is not None:
        return _gpu_context[1]
    
    vendor, backend = GPUSelector.select_best_backend()
    _gpu_context = (vendor, backend)
    
    return backend


def initialize_gpu(backend_name: Optional[str] = None, device_id: int = 0) -> GPUBackend:
    """Initialize a specific GPU backend.
    
    Args:
        backend_name: "cuda" | "opencl" | "vulkan" (auto-detect if None)
        device_id: Device ID to use
        
    Returns:
        Initialized GPU backend instance
    """
    global _gpu_context
    
    if backend_name is None:
        vendor, backend = GPUSelector.select_best_backend()
    else:
        # Force specific backend
        if backend_name == "cuda":
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but not available")
            return CUDABackend(device_id)
        elif backend_name == "opencl":
            try:
                import pyopencl as cl
                return OpenCLBackend(device_id)
            except ImportError:
                raise RuntimeError("OpenCL requested but pyopencl not installed")
        elif backend_name == "vulkan":
            try:
                import pyvulkan as vulkan
                return VulkanBackend(device_id)
            except ImportError:
                raise RuntimeError("Vulkan requested but pyvulkan not installed")
        else:
            raise ValueError(f"Unknown backend: {backend_name}")
    
    _gpu_context = (vendor, backend)
    return backend


def is_gpu_available() -> bool:
    """Check if GPU acceleration is available."""
    try:
        gpus = GPUSelector.detect_available_gpus()
        return any(gpu.is_available for gpu in gpus)
    except Exception:
        return False


def get_gpu_info() -> Dict[str, Any]:
    """Get information about the current GPU setup."""
    gpus = GPUSelector.detect_available_gpus()
    
    if not gpus:
        return {"available": False, "gpus": []}
    
    best_vendor, _ = GPUSelector.select_best_backend()
    
    return {
        "available": True,
        "best_gpu": {
            "vendor": best_vendor,
            "name": max(gpus, key=lambda g: (priority.get(g.vendor, 3), -g.memory_gb)).name,
            "memory_gb": max(gpus, key=lambda g: (priority.get(g.vendor, 3), -g.memory_gb)).memory_gb,
        },
        "all_gpus": [
            {
                "device_id": gpu.device_id,
                "vendor": gpu.vendor,
                "name": gpu.name,
                "memory_gb": gpu.memory_gb,
                "is_available": gpu.is_available,
            }
            for gpu in gpus
        ],
    }


# Convenience function for vendor-agnostic tensor operations
def to_gpu(data: np.ndarray) -> Any:
    """Convert numpy array to GPU tensor (vendor-agnostic)."""
    backend = get_gpu_backend()
    return backend.copy_to_gpu(data)


def from_gpu(gpu_tensor: Any) -> np.ndarray:
    """Convert GPU tensor back to numpy array (vendor-agnostic)."""
    backend = get_gpu_backend()
    return backend.copy_from_gpu(gpu_tensor)


# Priority mapping for vendor selection
_priority = {"nvidia": 0, "intel": 1, "arm": 2}
