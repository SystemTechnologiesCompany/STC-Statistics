import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings,Qt
from stc_statistics.app import MainWindow
from stc_statistics.pages import PAGE_KEYS
from stc_statistics.workbench import project_save,project_open
from stc_statistics.science import compute,pack_result
from stc_statistics.projects import clean_frame


class StudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        settings=QSettings(str(self.root/'settings.ini'),QSettings.Format.IniFormat)
        self.settings=patch('stc_statistics.app.QSettings',return_value=settings)
        self.settings.start(); self.addCleanup(self.settings.stop)
        self.window=MainWindow()
        self.addCleanup(self.close)
        rng=np.random.default_rng(42)
        self.frame=pd.DataFrame(rng.normal(size=(45,4)),columns=['X','Y','Z','V'])
        self.frame['Target']=self.frame.X*3+self.frame.Y**2
        self.window.use_frame(self.frame)

    def close(self):
        if self.window.science_busy:
            for page in self.window.studio_pages.values(): page.cancel()
            self.pump()
        self.window.dirty=False; self.window.close()
        self.app.processEvents()

    def pump(self,seconds=30):
        deadline=time.monotonic()+seconds
        while self.window.science_busy and time.monotonic()<deadline:
            self.app.processEvents(); time.sleep(.01)
        self.assertFalse(self.window.science_busy,'Worker did not finish')
        self.app.processEvents()

    def test_dedicated_pages_preserve_selection_and_translate(self):
        self.assertEqual(self.window.pages.count(),len(PAGE_KEYS))
        for key in ('maps','scene','relations','prediction'):
            self.window.navigate(key,False)
            self.assertEqual(self.window.pages.currentIndex(),PAGE_KEYS.index(key))
        page=self.window.studio_pages['prediction']
        page.fields['trees'].setValue(150)
        self.window.navigate('data'); self.window.navigate('prediction')
        self.assertEqual(page.fields['trees'].value(),150)
        self.window.language_picker.setCurrentIndex(1)
        self.assertEqual(page.make_button.text(),'Calculer')
        self.assertEqual(self.window.page_title.text(),'Prédiction')

    def test_real_process_computes_map_and_outputs_typed_tables_and_images(self):
        page=self.window.studio_pages['maps']; page.fields['resolution'].setValue(16)
        with patch('stc_statistics.studio.QMessageBox.warning') as warning:
            page.run(); self.assertTrue(self.window.science_busy)
            self.assertFalse(self.window.table.isEnabled())
            self.pump(); warning.assert_not_called()
        self.assertIsNotNone(page.result)
        self.assertEqual(self.window.current_page,'maps')
        self.assertTrue(any('image/png' in o.get('data',{}) for o in page.output_cell.outputs))
        self.assertIn('Grid values',page.result['tables'])
        self.window.language_picker.setCurrentIndex(1)
        self.assertEqual(page.make_button.text(),'Calculer')

    def test_cancelled_job_does_not_change_data_or_add_results(self):
        page=self.window.studio_pages['prediction']
        page.fields['trees'].setValue(500); page.fields['repeats'].setValue(10)
        original=self.window.frame.copy(deep=True); count=len(self.window.cells)
        page.run(); page.cancel(); self.pump()
        pd.testing.assert_frame_equal(self.window.frame,original)
        self.assertEqual(len(self.window.cells),count)
        self.assertIsNone(page.result)

    def test_project_roundtrip_preserves_live_scene_and_options_without_retraining(self):
        page=self.window.studio_pages['scene']
        options=dict(x='X',y='Y',z='Z',value='V',mode='surface',resolution=16,exaggeration=3.,language='en')
        page.restore_options(options)
        result=compute('scene',self.frame,options)
        page.display_result(result); page.record_result(pack_result(result),options)
        page.plots[0][1].axes[0].view_init(elev=42,azim=35)
        self.window.language_picker.setCurrentIndex(1)
        path=self.root/'roundtrip.stcp'; project_save(self.window,str(path))
        self.window.dirty=False
        with patch('stc_statistics.science.compute',side_effect=AssertionError('Must not recompute on open')):
            project_open(self.window,str(path))
        restored=self.window.studio_pages['scene']
        self.assertIsNotNone(restored.result)
        self.assertAlmostEqual(restored.plots[0][1].axes[0].elev,42)
        self.assertAlmostEqual(restored.plots[0][1].axes[0].azim,35)
        self.assertEqual(restored.fields['exaggeration'].value(),3)
        self.assertEqual(restored.plot_picker.currentText(),'Vue 3D')
        np.testing.assert_allclose(restored.result['field'],result['field'],equal_nan=True)

    def test_only_latest_interactive_payload_is_kept_per_workspace(self):
        page=self.window.studio_pages['relations']
        options={'columns':['X','Y','Target'],'mode':'heatmap','method':'pearson'}
        result=compute('relations',self.frame,options)
        page.display_result(result); page.record_result(pack_result(result),options)
        first=page.output_cell
        page.record_result(pack_result(result),options)
        self.assertIsNone(first.studio_payload)
        self.assertTrue(first.outputs)
        self.assertIsNotNone(page.output_cell.studio_payload)

    def test_profile_controls_and_live_camera_do_not_recompute_values(self):
        page=self.window.studio_pages['maps']
        self.assertFalse(page.fields['start_x'].isEnabled())
        page.fields['profile'].setChecked(True)
        self.assertTrue(page.fields['start_x'].isEnabled())
        scene=self.window.studio_pages['scene']
        options=dict(x='X',y='Y',z='Z',mode='surface',resolution=12,exaggeration=1.)
        scene.restore_options(options)
        result=compute('scene',self.frame,options)
        scene.display_result(result)
        original=result['field'].copy()
        scene.fields['exaggeration'].setValue(7)
        scene.fields['elevation'].setValue(46)
        self.assertEqual(scene.result['options']['exaggeration'],7)
        self.assertAlmostEqual(scene.plots[0][1].axes[0].elev,46)
        np.testing.assert_array_equal(original,scene.result['field'])

    def test_correlation_heatmap_is_rectangular_and_translates_without_changing_values(self):
        page=self.window.studio_pages['relations']
        result=compute('relations',self.frame,{'columns':['X','Y','Target'],'mode':'heatmap','method':'pearson'})
        page.display_result(result)
        original=result['correlation'].copy()
        figure=page.plots[0][1]
        self.assertEqual(figure.axes[0].get_aspect(),'auto')
        self.assertFalse(any('n=' in text.get_text() for text in figure.axes[0].texts))
        self.window.language_picker.setCurrentIndex(1)
        self.assertEqual(page.plot_picker.currentText(),'Carte des corrélations')
        self.assertIn('corrélation signée',figure._suptitle.get_text())
        pd.testing.assert_frame_equal(result['correlation'],original)
        self.window.language_picker.setCurrentIndex(0)
        self.assertEqual(page.plot_picker.currentText(),'Correlation heatmap')

    def test_decimal_comma_property_is_prepared_with_preview_then_selected(self):
        frame=pd.DataFrame({'Puits':['HR001','HR002','HR003','HR004'],
                            'X':[0.,1.,0.,1.],'Y':[0.,0.,1.,1.],'PER':['0,1','0,2','0,3','0,4']})
        self.window.use_frame(frame)
        page=self.window.studio_pages['maps']
        self.assertIsNone(page.fields['value'].currentData())
        with patch('stc_statistics.studio.QMessageBox.information') as info:
            page.run()
        self.assertIn('STC-SCI102',info.call_args.args[-1])
        self.assertFalse(self.window.science_busy)
        with patch('stc_statistics.workbench.clean') as cleaning:
            page.prepare_numbers()
        cleaning.assert_called_once_with(self.window,initial_columns=['PER'])
        fixed=clean_frame(frame,['PER'],operation='numeric')
        self.window.use_frame(fixed)
        self.assertEqual(page.fields['value'].currentData(),'PER')
        self.assertTrue(page.validate_spatial_columns(page.options()))
        result=compute('maps',fixed,dict(page.options(),resolution=12))
        self.assertEqual(len(result['points']),4)
        self.assertEqual(frame.PER.iloc[0],'0,1')
        self.assertEqual(fixed.PER.iloc[0],.1)

    def test_mixed_excel_coordinates_produce_actionable_message_before_worker(self):
        frame=pd.DataFrame({'Puits':['HR001','HR002','HR003'],
            'X':[0,'1,48','2,56'],'Y':[1,'2,99','0,74'],
            'epaisseur':['54,5','8,3','48,5']})
        self.window.use_frame(frame)
        page=self.window.studio_pages['maps']
        self.window.language_picker.setCurrentIndex(1)
        with patch('stc_statistics.studio.QMessageBox.information') as info,patch.object(pd.DataFrame,'to_parquet',side_effect=AssertionError('Must validate before snapshot')):
            page.run()
        message=info.call_args.args[-1]
        self.assertIn('Préparer les nombres',message)
        self.assertIn('STC-SCI102',message)
        self.assertIsNone(page.job)
        with patch('stc_statistics.workbench.clean') as cleaning: page.prepare_numbers()
        cleaning.assert_called_once_with(self.window,initial_columns=['X','Y','epaisseur'])

    def test_point_location_map_does_not_require_a_scalar(self):
        self.window.use_frame(pd.DataFrame({'X':[1.,2.,3.],'Y':[4.,5.,6.]}))
        page=self.window.studio_pages['maps']
        page.fields['mode'].setCurrentIndex(page.fields['mode'].findData('samples'))
        self.assertTrue(page.validate_spatial_columns(page.options()))
