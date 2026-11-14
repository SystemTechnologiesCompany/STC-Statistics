using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("STC Statistics")]
[assembly: AssemblyCompany("System Technologies Company")]
[assembly: AssemblyProduct("STC Statistics")]
[assembly: AssemblyVersion("_APP_VERSION_.0")]
[assembly: AssemblyFileVersion("_APP_VERSION_.0")]

internal static class PortableLauncher
{
    private const string PayloadHash = "_PAYLOAD_HASH_";

    private static string Quote(string value)
    {
        StringBuilder output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { slashes++; continue; }
            output.Append('\\', character == '"' ? slashes * 2 + 1 : slashes);
            output.Append(character);
            slashes = 0;
        }
        output.Append('\\', slashes * 2);
        return output.Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string home = Environment.GetEnvironmentVariable("STC_RUNTIME_HOME");
        if (String.IsNullOrEmpty(home))
            home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "STCStatistics");
        home = Path.GetFullPath(home);
        string runtime = Path.Combine(home, "runtime-" + PayloadHash.Substring(0, 16));
        try
        {
            Directory.CreateDirectory(home);
            using (Mutex gate = new Mutex(false, "Local\\STCStatistics-" + PayloadHash.Substring(0, 16)))
            {
                bool held = false;
                try
                {
                    try { held = gate.WaitOne(TimeSpan.FromMinutes(3)); }
                    catch (AbandonedMutexException) { held = true; }
                    if (!held) throw new IOException("The application is still preparing its runtime. Try again shortly.");
                    string marker = Path.Combine(runtime, ".complete");
                    if (!File.Exists(marker) || File.ReadAllText(marker) != PayloadHash)
                    {
                        Directory.CreateDirectory(runtime);
                        string prefix = Path.GetFullPath(runtime) + Path.DirectorySeparatorChar;
                        using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("stc_payload"))
                        using (ZipArchive archive = new ZipArchive(input, ZipArchiveMode.Read))
                        {
                            foreach (ZipArchiveEntry entry in archive.Entries)
                            {
                                string target = Path.GetFullPath(Path.Combine(runtime, entry.FullName.Replace('/', Path.DirectorySeparatorChar)));
                                if (!target.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                                    throw new InvalidDataException("Invalid packaged path.");
                                if (entry.FullName.EndsWith("/")) { Directory.CreateDirectory(target); continue; }
                                Directory.CreateDirectory(Path.GetDirectoryName(target));
                                using (Stream source = entry.Open())
                                using (FileStream destination = File.Create(target)) source.CopyTo(destination);
                            }
                        }
                        File.WriteAllText(marker, PayloadHash);
                    }
                }
                finally { if (held) gate.ReleaseMutex(); }
            }

            ProcessStartInfo start = new ProcessStartInfo();
            start.FileName = Path.Combine(runtime, "pythonw.exe");
            StringBuilder arguments = new StringBuilder("-B " + Quote(Path.Combine(runtime, "app", "main.py")));
            foreach (string argument in args) arguments.Append(" " + Quote(argument));
            start.Arguments = arguments.ToString();
            start.WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.WindowStyle = ProcessWindowStyle.Hidden;
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.EnvironmentVariables.Remove("PYTHONHOME");
            start.EnvironmentVariables.Remove("PYTHONPATH");
            start.EnvironmentVariables["STC_PORTABLE_ROOT"] = runtime;
            foreach (string[] setting in new string[][] {
                new string[]{"IPYTHONDIR", "ipython"}, new string[]{"JUPYTER_RUNTIME_DIR", "jupyter"}, new string[]{"MPLCONFIGDIR", "matplotlib"}})
            {
                string directory = Path.Combine(home, setting[1]);
                Directory.CreateDirectory(directory);
                start.EnvironmentVariables[setting[0]] = directory;
            }
            string log = Path.Combine(home, "app-" + Process.GetCurrentProcess().Id.ToString() + ".log");
            object logLock = new object();
            using (StreamWriter writer = new StreamWriter(log, true, Encoding.UTF8))
            using (Process process = new Process())
            {
                writer.AutoFlush = true;
                process.StartInfo = start;
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs data) { if (data.Data != null) lock(logLock) writer.WriteLine(data.Data); };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs data) { if (data.Data != null) lock(logLock) writer.WriteLine(data.Data); };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            try { File.AppendAllText(Path.Combine(home, "launcher-error.log"), error.ToString()); } catch { }
            if (Array.IndexOf(args, "--self-test") < 0)
                MessageBox.Show("STC Statistics could not start. / Impossible de demarrer STC Statistics.\n\n" + error.Message,
                                "STC Statistics", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
