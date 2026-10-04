using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Collections.Generic;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Plasticity 模型组件库")]
[assembly: System.Reflection.AssemblyProduct("Plasticity 模型组件库")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

internal static class Launcher {
    private static void Log(string root,string message) {
        if (root == null) return;
        try {
            string key;
            using(var hash=System.Security.Cryptography.SHA256.Create())
                key=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(root.ToUpperInvariant()))).Replace("-","");
            using(var mutex=new Mutex(false,"Local\\PlasticityAssetLauncherLog-"+key)) {
                bool owned=false;
                try {
                    try {owned=mutex.WaitOne(3000);} catch(AbandonedMutexException) {owned=true;}
                    if(owned) File.AppendAllText(Path.Combine(root,".runtime/launcher.log"),message,Encoding.UTF8);
                } finally {if(owned)mutex.ReleaseMutex();}
            }
        } catch(IOException) { } catch(UnauthorizedAccessException) { }
    }
    private static string FindRoot() {
        var folder = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
        for (int i = 0; folder != null && i < 3; i++, folder = folder.Parent) {
            if (File.Exists(Path.Combine(folder.FullName,"start.ps1")) &&
                File.Exists(Path.Combine(folder.FullName,"main.py"))) return folder.FullName;
        }
        throw new InvalidOperationException("找不到组件库项目。请将启动入口保留在项目目录或 .runtime 目录中。");
    }
    private static string Quote(string value) {
        // Windows file names cannot contain quotes; these arguments are file paths.
        return "\"" + value + "\"";
    }
    private sealed class LocalClient : WebClient {
        protected override WebRequest GetWebRequest(Uri uri) {
            var request = base.GetWebRequest(uri);
            request.Timeout = 1000;
            request.Proxy = null;
            return request;
        }
    }
    private static int ProbeBackend(string root) {
        try {
            var serializer = new JavaScriptSerializer();
            var metadata = serializer.Deserialize<Dictionary<string,object>>(
                File.ReadAllText(Path.Combine(root,".runtime/backend-instance.json")));
            int port = Convert.ToInt32(metadata["port"]);
            if (port < 1 || port > 65535) return 0;
            using (var client = new LocalClient()) {
                var health = serializer.Deserialize<Dictionary<string,object>>(
                    client.DownloadString("http://127.0.0.1:" + port + "/api/health"));
                if (Convert.ToString(health["app"]) == "plasticity-asset-tool") return Convert.ToInt32(metadata["pid"]);
            }
        } catch (Exception) { }
        return 0;
    }
    private static int WaitForBackend(string root) {
        var deadline = DateTime.UtcNow.AddSeconds(15);
        while (DateTime.UtcNow < deadline) {
            int owner = ProbeBackend(root);
            if (owner > 0) return owner;
            Thread.Sleep(50);
        }
        throw new InvalidOperationException("后台未在预期时间内连接。请查看 .runtime/service.log 和 .runtime/launcher.log。");
    }
    [STAThread]
    private static int Main(string[] args) {
        bool headless = Array.IndexOf(args,"--headless") >= 0;
        string root = null;
        try {
            foreach (string arg in args) if (arg != "--headless")
                throw new ArgumentException("不支持的启动参数：" + arg);
            root = FindRoot();
            Directory.CreateDirectory(Path.Combine(root,".runtime"));
            if (!File.Exists(Path.Combine(root,"plasticity-asset-tool-app/dist/index.html")))
                throw new InvalidOperationException("缺少组件库页面。请先运行 start.ps1 构建页面，再双击启动入口。");
            // The backend owns the instance lock and runtime checks. Start it
            // directly instead of spawning PowerShell and three Python probes.
            string python = null;
            foreach (string relative in new [] {"runtime/python/pythonw.exe", ".venv/Scripts/pythonw.exe",
                "runtime/python/python.exe", ".venv/Scripts/python.exe"}) {
                string candidate = Path.Combine(root,relative);
                if (File.Exists(candidate)) { python = candidate;break; }
            }
            if (python == null) throw new InvalidOperationException("缺少 Python 运行环境，请下载完整发布包或运行 start.ps1。");
            var info = new ProcessStartInfo(python,Quote(Path.Combine(root,"main.py")) +
                (headless ? " --headless" : "")) {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true
            };
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            int previousOwner = ProbeBackend(root);
            var started = Stopwatch.StartNew();
            using (var process = Process.Start(info)) {
                int owner = WaitForBackend(root);
                // Wait for an existing service reuse to finish. A Windows venv
                // redirector has a different PID from its long-lived Python
                // child, so PID inequality alone does not indicate reuse.
                if (previousOwner > 0 && owner == previousOwner && !process.WaitForExit(10000))
                    throw new InvalidOperationException("已有后台复用检查超时，请查看后台日志。");
                if (process.HasExited && process.ExitCode != 0)
                    throw new InvalidOperationException("后台启动失败，请查看 .runtime/service.log。");
            }
            Log(root,DateTime.Now.ToString("s") + " ready_ms="+started.ElapsedMilliseconds+"\r\n");
            return 0;
        } catch (Exception error) {
            Log(root,error + "\r\n");
            if (!headless) MessageBox.Show(error.Message,"Plasticity 模型组件库 · 启动失败",
                MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
