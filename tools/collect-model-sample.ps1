param([Parameter(Mandatory = $true)][string]$OutputFile)

# Read only the native Plasticity clipboard format. Use a disposable test box.
# No paste, document changes, network requests or clipboard writes.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class PatModelSample {
    [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern uint RegisterClipboardFormat(string name);
    [DllImport("user32.dll", SetLastError=true)] static extern bool OpenClipboard(IntPtr owner);
    [DllImport("user32.dll")] static extern bool CloseClipboard();
    [DllImport("user32.dll", SetLastError=true)] static extern IntPtr GetClipboardData(uint format);
    [DllImport("kernel32.dll", SetLastError=true)] static extern UIntPtr GlobalSize(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr GlobalLock(IntPtr handle);
    [DllImport("kernel32.dll")] static extern bool GlobalUnlock(IntPtr handle);
    public static byte[] Read() {
        uint format = RegisterClipboardFormat("application/vnd.plasticity.items");
        if (format == 0 || !OpenClipboard(IntPtr.Zero)) throw new Win32Exception();
        try {
            IntPtr handle = GetClipboardData(format);
            if (handle == IntPtr.Zero) throw new InvalidOperationException("Copy a selected test box in Plasticity first.");
            ulong size = GlobalSize(handle).ToUInt64();
            if (size == 0 || size > 64UL * 1024 * 1024) throw new InvalidOperationException("Model must be between 1 byte and 64 MB.");
            IntPtr pointer = GlobalLock(handle);
            if (pointer == IntPtr.Zero) throw new Win32Exception();
            try {
                byte[] data = new byte[(int)size];
                Marshal.Copy(pointer, data, 0, data.Length);
                return data;
            } finally { GlobalUnlock(handle); }
        } finally { CloseClipboard(); }
    }
}
'@
$sampleBytes = [PatModelSample]::Read()
$samplePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputFile)
# Never overwrite an existing file.
$sampleStream = [System.IO.File]::Open($samplePath, [System.IO.FileMode]::CreateNew)
try { $sampleStream.Write($sampleBytes, 0, $sampleBytes.Length) } finally { $sampleStream.Dispose() }
Write-Output "Saved $($sampleBytes.Length) bytes to $samplePath"
