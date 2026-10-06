using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("plasticity asset tool plugin installer")]
[assembly: AssemblyDescription("plasticityassettool 插件安装与升级；支持组件默认布尔置入")]
[assembly: AssemblyProduct("plasticity asset tool")]
[assembly: AssemblyCompany("plasticityassettool 开源项目")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

internal static class PluginInstaller {
    internal static string Quote(string value) {
        return "\"" + Regex.Replace(Regex.Replace(value, @"(\\*)""", "$1$1\\\""), @"(\\+)$", "$1$1") + "\"";
    }
    private static string Text(Dictionary<string,object> request, string key) {
        return Convert.ToString(request[key]);
    }
    private static bool IsAdministrator() {
        return new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator);
    }
    private static Form Details(Dictionary<string,object> request) {
        var form = new Form { Text="Plasticity 模型组件库 · 插件安装", ClientSize=new Size(610,380),
            StartPosition=FormStartPosition.CenterScreen, FormBorderStyle=FormBorderStyle.FixedDialog,
            MaximizeBox=false, MinimizeBox=false, Font=new Font("Microsoft YaHei UI",9F),
            BackColor=Color.FromArgb(28,28,28), ForeColor=Color.FromArgb(225,225,225) };
        form.Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        var title=new Label { Text="Plasticity 模型组件库插件", Bounds=new Rectangle(16,12,578,30), Font=new Font(form.Font.FontFamily,14F,FontStyle.Bold) };
        var details=new TextBox { Multiline=true, ReadOnly=true, BorderStyle=BorderStyle.None,
            Bounds=new Rectangle(16,52,578,267), BackColor=form.BackColor, ForeColor=form.ForeColor,
            ScrollBars=ScrollBars.Vertical,
            TabStop=false,
            Text="来源：plasticityassettool 开源项目\r\n" +
                "项目：https://github.com/mianxiu/plasticityassettool\r\n\r\n" +
                "本次操作："+Text(request,"description")+"\r\n" +
                "需要权限：更新 Plasticity 安装目录中的插件入口。\r\n" +
                "目标文件："+Text(request,"target")+"\r\n" +
                "回滚备份："+Text(request,"backup")+"\r\n\r\n" +
                "日常打开面板、保存和置入组件无需管理员权限。\r\n" +
                "此安装器未签名，Windows 仍可能显示“未知发布者”。" };
        var cancel=new Button { Text="取消", Bounds=new Rectangle(356,337,80,29), DialogResult=DialogResult.Cancel };
        var proceed=new Button { Text="继续，申请安装权限", Bounds=new Rectangle(442,337,152,29), DialogResult=DialogResult.OK };
        form.Controls.AddRange(new Control[]{title,details,cancel,proceed});
        form.AcceptButton=proceed;form.CancelButton=cancel;
        form.ActiveControl=proceed;
        return form;
    }
    private static int InstallCore(Dictionary<string,object> request) {
        if(!IsAdministrator())throw new InvalidOperationException("安装插件入口需要 Windows 管理员权限。");
        string root=Text(request,"root"), script=Path.Combine(root,"installer","main_embed_install.py");
        if(!File.Exists(script))throw new FileNotFoundException("找不到组件库安装脚本",script);
        var arguments=(System.Collections.IEnumerable)request["arguments"];
        var command=new StringBuilder("-m installer.main_embed_install");
        foreach(object value in arguments)command.Append(" ").Append(Quote(Convert.ToString(value)));
        var info=new ProcessStartInfo(Text(request,"python"),command.ToString()) {
            WorkingDirectory=root, UseShellExecute=false, CreateNoWindow=true,
            RedirectStandardOutput=true, RedirectStandardError=true,
            StandardOutputEncoding=Encoding.UTF8, StandardErrorEncoding=Encoding.UTF8 };
        info.EnvironmentVariables["PYTHONIOENCODING"]="utf-8";
        using(var process=Process.Start(info)) {
            string output=process.StandardOutput.ReadToEnd()+process.StandardError.ReadToEnd();
            process.WaitForExit();
            File.WriteAllText(Text(request,"result"),output,Encoding.UTF8);
            return process.ExitCode;
        }
    }
    private static int Install(Dictionary<string,object> request) {
        string identity;
        using(var hash=System.Security.Cryptography.SHA256.Create()) {
            identity=BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Path.GetFullPath(Text(request,"target")).ToUpperInvariant()))).Replace("-","");
        }
        using(var mutex=new Mutex(false,"Local\\PlasticityAssetPluginInstall-"+identity)) {
            bool owned=false;
            try {
                try {owned=mutex.WaitOne(0);} catch(AbandonedMutexException) {owned=true;}
                if(!owned)throw new InvalidOperationException("另一个安装器正在修改此版本，请等待它完成。");
                return InstallCore(request);
            } finally {if(owned)mutex.ReleaseMutex();}
        }
    }
    [STAThread]
    private static int Main(string[] args) {
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        try {
            if(args.Length<1)throw new ArgumentException("请使用项目中的 install-plugin.ps1 启动安装。");
            string requestPath=Path.GetFullPath(args[0]);
            var request=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(requestPath,Encoding.UTF8));
            if(args.Length>1 && args[1]=="--elevated")return Install(request);
            using(var form=Details(request)) {
                if(args.Length==3 && args[1]=="--preview-image") {
                    form.ShowInTaskbar=false;form.StartPosition=FormStartPosition.Manual;
                    form.Location=new Point(-32000,-32000);form.Show();form.Update();Application.DoEvents();
                    using(var bitmap=new Bitmap(form.Width,form.Height)) {
                        form.DrawToBitmap(bitmap,new Rectangle(0,0,form.Width,form.Height));
                        bitmap.Save(args[2],System.Drawing.Imaging.ImageFormat.Png);
                    }
                    form.Hide();
                    return 0;
                }
                if(form.ShowDialog()!=DialogResult.OK)return 1223;
            }
            int exitCode;
            if(IsAdministrator())exitCode=Install(request);
            else {
                var info=new ProcessStartInfo(Application.ExecutablePath,Quote(requestPath)+" --elevated") {
                    UseShellExecute=true,Verb="runas",WorkingDirectory=Text(request,"root") };
                using(var process=Process.Start(info)){process.WaitForExit();exitCode=process.ExitCode;}
            }
            if(exitCode==0)MessageBox.Show("插件安装成功，回滚备份已保留。\r\n下次启动 Plasticity 时生效。","Plasticity 模型组件库",MessageBoxButtons.OK,MessageBoxIcon.Information);
            else MessageBox.Show("插件安装未完成。\r\n详细结果："+Text(request,"result"),"Plasticity 模型组件库",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return exitCode;
        } catch(Win32Exception error) {
            if(error.NativeErrorCode==1223)return 1223;
            MessageBox.Show(error.Message,"Plasticity 模型组件库 · 安装错误");return 1;
        } catch(Exception error) {
            MessageBox.Show(error.Message,"Plasticity 模型组件库 · 安装错误");return 1;
        }
    }
}
