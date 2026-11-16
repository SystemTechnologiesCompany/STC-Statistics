using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("STC Statistics")]
[assembly: AssemblyCompany("System Technologies Company")]
[assembly: AssemblyProduct("STC Statistics")]
[assembly: AssemblyVersion("_APP_VERSION_.0")]
[assembly: AssemblyFileVersion("_APP_VERSION_.0")]

internal static class InstalledLauncher
{
    private static string Quote(string value)
    {
        StringBuilder output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            output.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
            output.Append(c);
            slashes = 0;
        }
        output.Append('\\', slashes * 2);
        return output.Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = Path.GetFullPath(AppDomain.CurrentDomain.BaseDirectory);
        string runtime = Path.Combine(root, "runtime");
        string overrideHome = Environment.GetEnvironmentVariable("STC_RUNTIME_HOME");
        string dataHome = String.IsNullOrEmpty(overrideHome)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "STCStatistics")
            : Path.GetFullPath(overrideHome);
        try
        {
            if (!File.Exists(Path.Combine(runtime, ".complete")) ||
                !File.Exists(Path.Combine(runtime, "pythonw.exe")) ||
                !File.Exists(Path.Combine(runtime, "app", "main.py")))
                throw new IOException("Incomplete installation");
            Directory.CreateDirectory(dataHome);
            string projects = String.IsNullOrEmpty(overrideHome)
                ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "STC Statistics")
                : Path.Combine(dataHome, "Projects");
            Directory.CreateDirectory(projects);
            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(runtime, "pythonw.exe");
            StringBuilder arguments = new StringBuilder("-B " + Quote(Path.Combine(runtime, "app", "main.py")));
            foreach (string arg in args) arguments.Append(" " + Quote(arg));
            start.Arguments = arguments.ToString();
            start.WorkingDirectory = projects;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.WindowStyle = ProcessWindowStyle.Hidden;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.EnvironmentVariables.Remove("PYTHONHOME");
            start.EnvironmentVariables.Remove("PYTHONPATH");
            start.EnvironmentVariables["STC_PORTABLE_ROOT"] = runtime;
            foreach (string name in new string[] { "IPYTHONDIR", "JUPYTER_RUNTIME_DIR", "MPLCONFIGDIR" })
            {
                string directory = Path.Combine(dataHome, name.ToLowerInvariant());
                Directory.CreateDirectory(directory);
                start.EnvironmentVariables[name] = directory;
            }
            object logLock = new object();
            string logPath = Path.Combine(dataHome, "installed-launcher.log");
            using (Mutex running = new Mutex(false, "Local\\STCStatisticsInstalled"))
            using (FileStream log = new FileStream(logPath, FileMode.OpenOrCreate, FileAccess.Write, FileShare.ReadWrite))
            using (StreamWriter writer = new StreamWriter(log, Encoding.UTF8))
            using (Process process = new Process())
            {
                log.Position = log.Length;
                writer.AutoFlush = true;
                process.StartInfo = start;
                DataReceivedEventHandler record = delegate(object sender, DataReceivedEventArgs data)
                {
                    if (data.Data == null) return;
                    lock (logLock)
                    {
                        if (log.Length > 2 * 1024 * 1024) { writer.Flush(); log.SetLength(0); log.Position = 0; }
                        writer.WriteLine(data.Data);
                    }
                };
                process.OutputDataReceived += record;
                process.ErrorDataReceived += record;
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            try
            {
                Directory.CreateDirectory(dataHome);
                string path = Path.Combine(dataHome, "installed-startup.log");
                if (File.Exists(path) && new FileInfo(path).Length > 1024 * 1024) File.WriteAllText(path, "");
                File.AppendAllText(path, DateTime.UtcNow.ToString("o") + " " + error.ToString() + Environment.NewLine);
            }
            catch { }
            if (Array.IndexOf(args, "--self-test") < 0)
                MessageBox.Show("STC Statistics could not start. Please run Setup again or contact STC.\n" +
                    "Impossible de demarrer STC Statistics. Relancez l'installation ou contactez STC.\n\nSTC-S001",
                    "STC Statistics", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
