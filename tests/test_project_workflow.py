import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop,QTimer
from stc_statistics.app import MainWindow
from stc_statistics.workbench import project_save,project_open
from stc_statistics.kernel import Execution,Session


class ProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_saved_workspace_restores_without_running(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'test.stcp')
            window=MainWindow()
            window.use_frame(pd.DataFrame({'x':[1.,2.,3.]}))
            cell=window.add_cell("raise RuntimeError('must not run on open')")
            import nbformat
            cell.outputs=[nbformat.v4.new_output('stream',name='stdout',text='Saved result')]
            window.chart_options={'bins':23}
            window.correlation_method.setCurrentIndex(1)
            window.chart_picker.setCurrentIndex(2)
            window.report_text.setChecked(False)
            with patch('stc_statistics.workbench.QFileDialog.getSaveFileName',return_value=(path,'')):
                self.assertTrue(project_save(window))
            window.frame.iloc[0,0]=99
            window.correlation_method.setCurrentIndex(0)
            window.chart_picker.setCurrentIndex(0)
            window.report_text.setChecked(True)
            window.dirty=False
            with patch('stc_statistics.workbench.QFileDialog.getOpenFileName',return_value=(path,'')):
                project_open(window)
            self.assertEqual(window.frame.iloc[0,0],1)
            self.assertEqual(window.cells[0].outputs[0].text,'Saved result')
            self.assertEqual(window.chart_options['bins'],23)
            self.assertEqual(window.correlation_method.currentData(),'spearman')
            self.assertEqual(window.chart_picker.currentData(),'scatter')
            self.assertFalse(window.report_text.isChecked())
            self.assertIsNone(window.session.manager)
            window.dirty=False
            window.close()

    def test_kernel_bridge_updates_both_directions(self):
        session=Session()
        try:
            with tempfile.TemporaryDirectory() as folder:
                path=str(Path(folder)/'df.parquet')
                pd.DataFrame({'x':[1,2,3]}).to_parquet(path)
                worker=Execution(session,"df['x'] = df.x * 2\nprint(df.x.mean())",load_path=path,snapshot_path=path)
                loop=QEventLoop()
                messages,results,paths=[],[],[]
                worker.output.connect(messages.append)
                worker.completed.connect(lambda success,count:results.append(success))
                worker.data_ready.connect(paths.append)
                worker.finished.connect(loop.quit)
                timer=QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(session.interrupt)
                timer.start(65000)
                worker.start()
                loop.exec()
                worker.wait()
                timer.stop()
                self.assertEqual(results,[True],messages)
                self.assertEqual(paths,[path])
                self.assertEqual(pd.read_parquet(path).x.tolist(),[2,4,6])
                self.assertTrue(any('4.0' in m['content'].get('text','') for m in messages))
        finally:
            session.close()

    def test_legacy_projects_open_and_save_as_stcp_without_overwriting_original(self):
        import nbformat
        from stc_statistics.projects import save_project,load_project
        for suffix in ('.stcproj','.stcproject'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as folder:
                legacy=Path(folder)/('old'+suffix)
                frame=pd.DataFrame({'x':[1,2,3]})
                save_project(legacy,frame,nbformat.v4.new_notebook(),{})
                original=legacy.read_bytes()
                window=MainWindow()
                project_open(window,path=str(legacy))
                with patch('stc_statistics.workbench.QFileDialog.getSaveFileName',return_value=(str(legacy),'')) as picker:
                    self.assertTrue(project_save(window))
                    self.assertTrue(picker.call_args.args[2].endswith('.stcp'))
                    self.assertEqual(picker.call_args.args[3],'STC (*.stcp)')
                new=legacy.with_suffix('.stcp')
                self.assertEqual(window.project_path,str(new))
                self.assertEqual(legacy.read_bytes(),original)
                restored,_,_=load_project(new)
                pd.testing.assert_frame_equal(frame,restored)
                window.dirty=False
                window.close()

    def test_report_builder_selection_comments_and_restore(self):
        import nbformat
        from stc_statistics.workbench import report_builder
        from PySide6.QtWidgets import QListWidget,QPlainTextEdit,QDialogButtonBox
        window=MainWindow()
        cell=window.add_cell('print(42)')
        cell.outputs=[nbformat.v4.new_output('stream',name='stdout',text='42')]
        errors=[]
        def interact():
            d=QApplication.activeModalWidget()
            try:
                listing=d.findChild(QListWidget)
                self.assertEqual(listing.count(),1)
                listing.setCurrentRow(0)
                edits=d.findChildren(QPlainTextEdit)
                edits[0].setPlainText('Result comment')
                edits[1].setPlainText('Introduction')
                d.findChild(QDialogButtonBox).accepted.emit()
            except Exception as exc:
                errors.append(exc)
                d.reject()
        QTimer.singleShot(50,interact)
        report_builder(window)
        self.assertFalse(errors,errors)
        self.assertEqual(window.report_plan[0]['annotations']['0'],'Result comment')
        self.assertEqual(window.report_plan[0]['indices'],[0])
        QTimer.singleShot(50,interact)
        report_builder(window)
        self.assertFalse(errors,errors)
        window.dirty=False
        window.close()


if __name__=='__main__':
    unittest.main()
