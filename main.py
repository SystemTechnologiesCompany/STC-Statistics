"""Desktop entry point, including the bundled notebook-kernel subprocess."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if '--stc-kernel' in sys.argv:
        sys.argv.remove('--stc-kernel')
        from ipykernel.kernelapp import IPKernelApp
        IPKernelApp.launch_instance()
    elif '--self-test' in sys.argv:
        from stc_statistics.selftest import run
        sys.exit(run(sys.argv[sys.argv.index('--self-test') + 1]))
    else:
        from stc_statistics.app import main
        main()
