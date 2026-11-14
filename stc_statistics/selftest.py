"""Packaged-app diagnostics; never runs on an ordinary desktop launch."""
import base64
import io
import json
from pathlib import Path
import sys
import traceback


def run(output):
    report = {'frozen': bool(getattr(sys, 'frozen', False)), 'executable': sys.executable}
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import os
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import pandas as pd
        import openpyxl
        import xlrd
        import nbformat
        import ipykernel
        from ipykernel.kernelapp import IPKernelApp
        import jupyter_client
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from .app import MainWindow
        from .theme import STYLE, initialize_fonts
        from .analysis import summarize
        from .reports import export_excel, export_word
        from .pages import LOGO_PATH
        from .kernel import kernel_command
        from .advanced import advanced_analysis
        from .projects import save_project, load_project
        app = QApplication.instance() or QApplication([])
        initialize_fonts(app)
        app.setStyleSheet(STYLE)
        window = MainWindow()
        window.setProperty('reduceMotion', True)
        window.resize(1350, 738)
        window.show()
        data = pd.DataFrame({'A': [1, 2, 3], 'B': [2, 4, 6]})
        window.use_frame(data)
        assert summarize(data, ['A'])['A'].iloc[2] == 2
        ci, notes = advanced_analysis(data, 'ci', ['A'])
        assert ci.iloc[0,1] == 2
        pca, notes = advanced_analysis(data, 'pca', ['A','B'])
        assert pca.shape == (2,2)
        project_path = path.with_suffix('.stcproj')
        save_project(project_path, data, nbformat.v4.new_notebook(), {'chart':{'bins':15}})
        restored, _, _ = load_project(project_path)
        pd.testing.assert_frame_equal(data, restored)
        assert not window.windowIcon().isNull()
        assert LOGO_PATH.is_file()
        window.navigate('exports')
        QTest.qWait(120)
        window.grab().save(str(path.with_suffix('.png')))
        fig, ax = plt.subplots()
        ax.plot(data['A'], data['B'])
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png')
        plt.close(fig)
        items = [{'kind': 'table', 'title': 'Statistics', 'rows': [['Metric', 'A'], ['Mean', 2.0]]},
                 {'kind': 'image', 'title': 'Graph', 'png': buffer.getvalue()}]
        export_excel(path.with_suffix('.xlsx'), items)
        export_word(path.with_suffix('.docx'), items, logo=LOGO_PATH)
        report.update({'statistics': 'passed', 'advanced_statistics':'passed', 'projects':'passed', 'gui': 'passed', 'graphs': 'passed', 'word_export': 'passed',
                       'excel_export': 'passed', 'kernel_command': kernel_command(),
                       'ipykernel_import': 'passed', 'version': __import__('stc_statistics.version', fromlist=['APP_VERSION']).APP_VERSION})
        window.dirty = False
        window.close()
        report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1
