import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
from PySide6.QtWidgets import QApplication
from stc_statistics.app import MainWindow
from stc_statistics.i18n import TEXT
from stc_statistics.workbench import advanced,geo,report_builder
from make_patch import build_patch


class UiReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def window(self):
        w=MainWindow()
        w.language_picker.setCurrentIndex(0)
        self.addCleanup(lambda:(setattr(w,'dirty',False),w.close()))
        return w

    def test_update_guidance_matches_current_actions_in_both_languages(self):
        w=self.window()
        page=w.updates_page
        self.assertFalse(page.download_button.isEnabled())
        for language in (0,1):
            w.language_picker.setCurrentIndex(language)
            text=page.how_text.text()
            self.assertIn(w.t('check_updates'),text)
            self.assertIn(w.t('install_update'),text)
            self.assertNotIn('Setup',text)
            self.assertNotIn('ZIP',text)
            self.assertNotIn('Legacy',text)
        self.assertEqual(set(TEXT['en']),set(TEXT['fr']))

    def test_close_prompt_and_export_description_match_project_workflow(self):
        w=self.window()
        for language in (0,1):
            w.language_picker.setCurrentIndex(language)
            self.assertIn('proje',w.t('unsaved').lower())
            self.assertIn('Word',w.t('exports_description'))
            self.assertNotIn('first',w.t('preview'))

    def test_project_dataset_is_not_labelled_as_sample(self):
        w=self.window()
        w.use_frame(pd.DataFrame({'x':[1,2]}))
        w.project_path='research.stcp'
        w.update_info()
        self.assertIn('research.stcp',w.dataset_badge.text())
        self.assertNotIn('sample',w.data_info.text())

    def test_reload_requires_a_source_and_follows_busy_state(self):
        w=self.window()
        self.assertFalse(w.reload_button.isEnabled())
        w.file_path='original.csv'
        w.set_busy(False)
        self.assertTrue(w.reload_button.isEnabled())
        w.set_busy(True)
        self.assertFalse(w.reload_button.isEnabled())
        w.set_busy(False)
        self.assertTrue(w.reload_button.isEnabled())

    def test_failed_import_retains_previous_data_and_hides_details(self):
        w=self.window()
        frame=pd.DataFrame({'x':[1,2]})
        w.use_frame(frame)
        w.file_path='broken.xlsx'
        w._previous_file_path='original.xlsx'
        with patch('stc_statistics.feedback.QMessageBox.warning') as warning:
            w.import_failed('Internal import trace C:/private/file.xlsx')
        self.assertEqual(w.file_path,'original.xlsx')
        pd.testing.assert_frame_equal(w.frame,frame)
        self.assertIn('STC-F101',warning.call_args.args[2])
        self.assertNotIn('private',warning.call_args.args[2])

    def test_pca_ignores_fields_for_other_methods(self):
        w=self.window()
        w.use_frame(pd.DataFrame({'x':[1,2,3],'y':[3,4,8]}))
        options={'method':'pca','response':'y','confidence':'not applicable','reference':'not applicable','clusters':'not applicable'}
        with patch('stc_statistics.workbench.choose',return_value=options),patch('stc_statistics.advanced.recipe',return_value='pca_result = 1') as recipe:
            advanced(w)
        self.assertEqual(len(w.cells),1)
        self.assertEqual(recipe.call_args.kwargs,{})

    def test_geology_uses_distinct_numeric_defaults(self):
        w=self.window()
        w.use_frame(pd.DataFrame({'sample':['a','b'],'phi':[10.,20.],'k':[1.,2.]}))
        with patch('stc_statistics.workbench.choose',return_value=None) as choose:
            geo(w)
        entries={key:values for key,label,values in choose.call_args.args[2]}
        self.assertEqual(entries['first'][0][1],'phi')
        self.assertEqual(entries['second'][0][1],'k')

    def test_empty_report_explains_what_to_do(self):
        w=self.window()
        with patch('stc_statistics.workbench.QMessageBox.information') as info,patch('stc_statistics.workbench.dialog') as dialog:
            report_builder(w)
        self.assertIn(w.t('no_report_results'),info.call_args.args)
        dialog.assert_not_called()

    def test_release_tag_case_is_preserved(self):
        import json
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as folder,patch('stc_statistics.licensing.require_configured_release'):
            _,feed=build_patch(root,folder,'99.0.0',['0.5.4'],tag='V99.0.0')
            payload=json.loads(feed.read_text())
            self.assertIn('/V99.0.0/',payload['download_url'])
            self.assertEqual(payload['release_tag'],'V99.0.0')


if __name__=='__main__':
    unittest.main()
