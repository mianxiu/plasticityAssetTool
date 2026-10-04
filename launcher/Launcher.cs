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
    private static void WaitForBackend(string root) {
        var serializer = new JavaScriptSerializer();
        var deadline = DateTime.UtcNow.AddSeconds(15);
        while (DateTime.UtcNow < deadline) {
            try {
                var metadata = serializer.Deserialize<Dictionary<string,object>>(
                    File.ReadAllText(Path.Combine(root,".runtime/backend-instance.json")));
                int port = Convert.ToInt32(metadata["port"]);
                if (port < 1 || port > 65535) throw new InvalidDataException("无效的后台端口");
                using (var client = new LocalClient()) {
                    var health = serializer.Deserialize<Dictionary<string,object>>(
                        client.DownloadString("http://127.0.0.1:" + port + "/api/health"));
                    if (Convert.ToString(health["app"]) == "plasticity-asset-tool") return;
                }
            } catch (Exception) { }
            Thread.Sleep(250);
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
            string powershell = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),
                "WindowsPowerShell/v1.0/powershell.exe");
            var info = new ProcessStartInfo(powershell,
                "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File " +
                Quote(Path.Combine(root,"start.ps1")) + " -NoBuild" + (headless ? " -Headless" : "")) {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            using (var process = Process.Start(info)) {
                var gate = new object();
                var output = new StringBuilder();var errors = new StringBuilder();
                process.OutputDataReceived += (sender,eventArgs) => { if(eventArgs.Data != null) lock(gate) output.AppendLine(eventArgs.Data); };
                process.ErrorDataReceived += (sender,eventArgs) => { if(eventArgs.Data != null) lock(gate) errors.AppendLine(eventArgs.Data); };
                process.BeginOutputReadLine();process.BeginErrorReadLine();
                if (!process.WaitForExit(30000)) {
                    process.Kill();
                    throw new InvalidOperationException("启动检查超时，请查看后台日志后重试。");
                }
                // A detached backend may retain inherited handles. Finish on
                // the starter's exit rather than waiting indefinitely for EOF.
                Thread.Sleep(100);
                try {process.CancelOutputRead();} catch(InvalidOperationException) { }
                try {process.CancelErrorRead();} catch(InvalidOperationException) { }
                string outputText,errorText;
                lock(gate) {outputText=output.ToString();errorText=errors.ToString();}
                Log(root,DateTime.Now.ToString("s") + "\r\n" + outputText + errorText);
                if (process.ExitCode != 0) throw new InvalidOperationException(
                    "组件库启动失败。\r\n" + errorText + "\r\n详细日志：.runtime/launcher.log");
            }
            WaitForBackend(root);
            return 0;
        } catch (Exception error) {
            Log(root,error + "\r\n");
            if (!headless) MessageBox.Show(error.Message,"Plasticity 模型组件库 · 启动失败",
                MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
