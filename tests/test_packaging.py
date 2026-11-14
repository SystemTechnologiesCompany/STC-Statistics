import sys
import unittest
from unittest.mock import patch
from stc_statistics.kernel import kernel_command


class PackagingTests(unittest.TestCase):
    def test_frozen_kernel_uses_executable_dispatcher(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', r'C:\App\STC Statistics.exe'):
            self.assertEqual(kernel_command(), [r'C:\App\STC Statistics.exe', '--stc-kernel', '-f', '{connection_file}'])

    def test_source_kernel_uses_its_python_interpreter(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(kernel_command(), [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'])


if __name__ == '__main__':
    unittest.main()
