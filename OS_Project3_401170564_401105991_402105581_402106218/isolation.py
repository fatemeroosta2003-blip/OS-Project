import ctypes
import os

CLONE_NEWNS   = 0x00020000
CLONE_NEWUTS  = 0x04000000
CLONE_NEWIPC  = 0x08000000
CLONE_NEWNET  = 0x40000000

def apply_isolation():
    libc = ctypes.CDLL('libc.so.6')
    flags = CLONE_NEWNS | CLONE_NEWUTS | CLONE_NEWIPC | CLONE_NEWNET
    if libc.unshare(flags) != 0:
        raise OSError("Failed to create namespaces.")

def set_container_hostname(hostname):
    libc = ctypes.CDLL('libc.so.6')
    libc.sethostname(hostname.encode(), len(hostname))
