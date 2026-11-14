"""A real, separate IPython kernel; all execution stays off the GUI thread."""
import queue
import sys
import time
import asyncio
import warnings

# Jupyter's synchronous adapters create background loops. On Windows 3.14,
# Proactor loop finalization can close a native handle twice after Qt workers exit.
# Use the selector policy also recommended for ZeroMQ's reader callbacks.
if sys.platform == 'win32' and hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from jupyter_client import KernelManager
from PySide6.QtCore import QThread, Signal


class Session:
    def __init__(self):
        self.manager = None
        self.client = None

    def ready(self):
        if self.manager is None:
            manager = KernelManager(kernel_name="python3")
            # Always use this app's environment, even if another Jupyter kernel is installed.
            manager.kernel_spec.argv = kernel_command()
            self.manager = manager
            manager.start_kernel()
            self.client = manager.blocking_client()
            self.client.start_channels()
            self.client.wait_for_ready(timeout=45)

    def interrupt(self):
        if self.manager is not None:
            self.manager.interrupt_kernel()

    def close(self):
        if self.manager is not None:
            try:
                self.manager.shutdown_kernel(now=True)
            finally:
                if self.client is not None:
                    self.client.stop_channels()
                self.client = self.manager = None


def kernel_command():
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--stc-kernel', '-f', '{connection_file}']
    return [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']


class Execution(QThread):
    output = Signal(dict)
    completed = Signal(bool, int)
    data_ready = Signal(str)

    def __init__(self, session, code, parent=None, load_path=None, snapshot_path=None):
        super().__init__(parent)
        self.session, self.code = session, code
        self.load_path, self.snapshot_path = load_path, snapshot_path

    def internal(self, code):
        client = self.session.client
        msg_id = client.execute(code, silent=True, store_history=False, allow_stdin=False)
        deadline = time.monotonic()+60
        error = None
        while time.monotonic() < deadline:
            try:
                msg = client.get_iopub_msg(timeout=.25)
            except queue.Empty:
                continue
            if msg.get('parent_header',{}).get('msg_id') != msg_id:
                continue
            kind, content = msg['header']['msg_type'],msg['content']
            if kind == 'error':
                error = content.get('evalue','Dataset synchronization failed')
            if kind == 'status' and content['execution_state']=='idle':
                if error:
                    raise RuntimeError(error)
                return
        raise TimeoutError('Dataset synchronization timed out')

    def run(self):
        success, count = True, 0
        try:
            self.session.ready()
            if self.load_path:
                self.internal(f"import pandas as _stc_pd\ndf = _stc_pd.read_parquet({self.load_path!r})")
            client = self.session.client
            msg_id = client.execute(self.code, allow_stdin=False, stop_on_error=True)
            start = time.monotonic()
            interrupted = False
            while True:
                elapsed = time.monotonic() - start
                if elapsed > 120 and not interrupted:
                    self.session.interrupt()
                    interrupted = True
                if elapsed > 135:
                    raise TimeoutError("Execution timed out. Restart Python before continuing.")
                try:
                    msg = client.get_iopub_msg(timeout=0.25)
                except queue.Empty:
                    if not self.session.manager.is_alive():
                        raise RuntimeError("Python stopped. Restart Python to continue.")
                    continue
                if msg.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                kind, content = msg["header"]["msg_type"], msg["content"]
                if kind == "execute_input":
                    count = content["execution_count"]
                elif kind in ("stream", "display_data", "execute_result", "error", "clear_output"):
                    self.output.emit({"msg_type": kind, "content": content})
                    if kind == "error":
                        success = False
                elif kind == "status" and content["execution_state"] == "idle":
                    break
        except Exception as exc:
            success = False
            self.output.emit({"msg_type": "error", "content": {
                "ename": type(exc).__name__, "evalue": str(exc), "traceback": []}})
        if self.snapshot_path:
            try:
                self.internal(f"import pandas as _stc_pd\nif isinstance(globals().get('df'), _stc_pd.DataFrame):\n    df.to_parquet({self.snapshot_path!r}, index=True)\nelse:\n    raise ValueError('df must remain a pandas DataFrame / df doit rester un DataFrame')")
                self.data_ready.emit(self.snapshot_path)
            except Exception as exc:
                success = False
                self.output.emit({'msg_type':'error','content':{'ename':'DataSyncError','evalue':str(exc),'traceback':[]}})
        self.completed.emit(success, count)
