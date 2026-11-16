"""Windows-owned credential protection and RSA-PSS verification; no added client wheels."""
import ctypes
from ctypes import wintypes
import hashlib
import os
import struct


def _windows():
    if os.name!='nt':
        raise OSError('Windows licensing protection is required')


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def protect(raw, decrypt=False):
    _windows()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    buf=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)))
    result=Blob()
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result))
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        # No LOCAL_MACHINE flag: bind to the current Windows user as well as PC.
        ok=fn(ctypes.byref(source),'STC Statistics activation',None,None,None,1,ctypes.byref(result))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data,result.size)
    finally:
        kernel.LocalFree(result.data)


def current_user_sid():
    _windows()
    adv=ctypes.WinDLL('advapi32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    adv.OpenProcessToken.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(wintypes.HANDLE)]
    adv.GetTokenInformation.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    adv.ConvertSidToStringSidW.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.LPWSTR)]
    handle=wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(handle)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        length=wintypes.DWORD()
        adv.GetTokenInformation(handle,1,None,0,ctypes.byref(length))
        buffer=ctypes.create_string_buffer(length.value)
        if not adv.GetTokenInformation(handle,1,buffer,length,ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid=ctypes.cast(buffer,ctypes.POINTER(ctypes.c_void_p))[0]
        text=wintypes.LPWSTR()
        if not adv.ConvertSidToStringSidW(sid,ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(ctypes.cast(text,ctypes.c_void_p))
    finally:
        kernel.CloseHandle(handle)


def device_id():
    _windows()
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
        guid,_=winreg.QueryValueEx(key,'MachineGuid')
    sid=current_user_sid()
    return hashlib.sha256(('STCStatistics/license/v1\0'+str(guid)+'\0'+sid).encode()).hexdigest()


def verify_signature(public_key, message, signature):
    """Use Windows CNG RSA-PSS/SHA256, with a fixed 32-byte PSS salt."""
    _windows()
    n=int(public_key['n'],16)
    e=int(public_key['e'])
    if n.bit_length()!=3072 or e!=65537 or len(signature)!=384:
        return False
    exponent=e.to_bytes(3,'big')
    modulus=n.to_bytes(384,'big')
    raw=struct.pack('<6I',0x31415352,3072,len(exponent),len(modulus),0,0)+exponent+modulus
    bcrypt=ctypes.WinDLL('bcrypt')
    pointer=ctypes.c_void_p
    bcrypt.BCryptOpenAlgorithmProvider.argtypes=[ctypes.POINTER(pointer),wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD]
    bcrypt.BCryptImportKeyPair.argtypes=[pointer,pointer,wintypes.LPCWSTR,ctypes.POINTER(pointer),pointer,wintypes.ULONG,wintypes.ULONG]
    bcrypt.BCryptVerifySignature.argtypes=[pointer,pointer,pointer,wintypes.ULONG,pointer,wintypes.ULONG,wintypes.ULONG]
    bcrypt.BCryptDestroyKey.argtypes=[pointer]
    bcrypt.BCryptCloseAlgorithmProvider.argtypes=[pointer,wintypes.ULONG]
    algorithm=pointer()
    key=pointer()
    if bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm),'RSA',None,0)!=0:
        raise OSError('Cannot initialize Windows signature verification')
    try:
        blob=ctypes.create_string_buffer(raw)
        if bcrypt.BCryptImportKeyPair(algorithm,None,'RSAPUBLICBLOB',ctypes.byref(key),blob,len(raw),0)!=0:
            raise OSError('Cannot load the license verification key')
        class Pss(ctypes.Structure):
            _fields_=[('algorithm',wintypes.LPCWSTR),('salt_bytes',wintypes.ULONG)]
        padding=Pss('SHA256',32)
        digest=ctypes.create_string_buffer(hashlib.sha256(message).digest())
        signed=ctypes.create_string_buffer(signature)
        return bcrypt.BCryptVerifySignature(key,ctypes.byref(padding),digest,32,signed,len(signature),8)==0
    finally:
        if key.value:
            bcrypt.BCryptDestroyKey(key)
        bcrypt.BCryptCloseAlgorithmProvider(algorithm,0)
