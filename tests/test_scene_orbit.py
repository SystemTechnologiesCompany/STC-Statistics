import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from matplotlib.backend_bases import MouseEvent
from stc_statistics.app import MainWindow
from stc_statistics.science import compute
from stc_statistics.workbench import project_save,project_open


class OrbitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        settings=QSettings(str(Path(self.temp.name)/'settings.ini'),QSettings.Format.IniFormat)
        with patch('stc_statistics.app.QSettings',return_value=settings): self.window=MainWindow()
        self.addCleanup(self.close)
        rng=np.random.default_rng(42)
        self.frame=pd.DataFrame({'X':530000+rng.uniform(0,50000,90),'Y':240000+rng.uniform(0,40000,90)})
        self.frame['Z']=-1500+25*np.sin(self.frame.X/7000)
        self.window.use_frame(self.frame)
        self.page=self.window.studio_pages['scene']
        options=dict(x='X',y='Y',z='Z',mode='surface',resolution=40,exaggeration=40.)
        self.page.restore_options(options); self.result=compute('scene',self.frame,options)
        self.page.display_result(self.result)
        self.canvas=self.page.plots[0][1].canvas; self.canvas.resize(850,500); self.canvas.draw()
        self.orbit=self.canvas._stc_orbit; self.ax=self.orbit.ax

    def close(self):
        self.window.dirty=False; self.window.close(); self.app.processEvents()

    def event(self,name,x,y,button=1,step=0):
        event=MouseEvent(name,self.canvas,x,y,button=button,step=step)
        self.canvas.callbacks.process(name,event)
        return event

    def pivot(self):
        return np.array([sum(getter())/2 for getter in (self.ax.get_xlim3d,self.ax.get_ylim3d,self.ax.get_zlim3d)])

    def test_dense_motion_is_coalesced_and_returns_full_detail_with_fixed_pivot(self):
        box=self.ax.bbox; x,y=box.x0+box.width*.5,box.y0+box.height*.5
        pivot=self.pivot(); bounds=self.ax.get_position().bounds; data=self.result['field'].copy()
        from mpl_toolkits.mplot3d.proj3d import proj_transform
        screen_pivot=self.ax.transData.transform(proj_transform(*pivot,self.ax.get_proj())[:2])
        self.event('button_press_event',x,y)
        with patch.object(self.canvas,'draw_idle') as draw:
            for delta in range(1,90): self.event('motion_notify_event',x+delta,y+delta/3)
            self.assertEqual(draw.call_count,0,'Native 3D motion must not flood full-frame redraws')
            self.assertTrue(self.orbit.timer.isActive())
            self.assertTrue(self.orbit.preview.get_visible())
            self.assertFalse(self.ax._axis3don)
            self.assertFalse(any(a.get_visible() for a,visible in self.orbit.artists))
            self.orbit.flush()
            self.assertEqual(draw.call_count,1)
        self.event('button_release_event',x+90,y+30)
        self.assertFalse(self.orbit.preview.get_visible())
        self.assertTrue(self.ax._axis3don)
        self.assertTrue(all(a.get_visible()==visible for a,visible in self.orbit.artists))
        self.assertEqual(self.ax.roll,0)
        self.assertNotAlmostEqual(self.ax.azim,-60)
        self.canvas.draw()
        np.testing.assert_allclose(self.pivot(),pivot,atol=1e-9)
        np.testing.assert_allclose(self.ax.get_position().bounds,bounds,atol=1e-12)
        np.testing.assert_allclose(self.ax.transData.transform(proj_transform(*pivot,self.ax.get_proj())[:2]),screen_pivot,atol=1e-7)
        np.testing.assert_array_equal(self.result['field'],data)

    def test_drag_location_does_not_change_orbit_sensitivity_or_roll(self):
        box=self.ax.bbox; changes=[]
        for fraction in (.3,.7):
            self.orbit.reset(); x=box.x0+box.width*fraction; y=box.y0+box.height*.5
            self.event('button_press_event',x,y)
            self.event('motion_notify_event',x+30,y+15)
            self.event('button_release_event',x+30,y+15)
            changes.append((self.ax.elev,self.ax.azim,self.ax.roll))
        np.testing.assert_allclose(changes[0],changes[1])

    def test_zoom_exaggeration_reset_and_project_restore_keep_centre(self):
        pivot=self.pivot(); self.orbit.change_zoom(1.5)
        self.page.fields['exaggeration'].setValue(60)
        self.assertEqual(self.orbit.zoom,1.5)
        self.page.record_result(__import__('stc_statistics.science',fromlist=['pack_result']).pack_result(self.result),self.page.options())
        path=Path(self.temp.name)/'orbit.stcp'; project_save(self.window,str(path))
        self.window.dirty=False; project_open(self.window,str(path))
        page=self.window.studio_pages['scene']; restored=page.plots[0][1].canvas._stc_orbit
        self.assertEqual(restored.zoom,1.5)
        self.assertEqual(page.fields['exaggeration'].value(),60)
        restored.reset(); self.assertEqual(restored.zoom,1)
        np.testing.assert_allclose([sum(b)/2 for b in restored.bounds],pivot)

    def test_release_outside_and_disposal_restore_or_stop_preview(self):
        self.orbit.press(SimpleNamespace(button=1,inaxes=self.ax,x=100,y=100))
        self.orbit.motion(SimpleNamespace(x=140,y=120))
        self.orbit.leave(None)
        self.assertIsNone(self.orbit.drag); self.assertFalse(self.orbit.previewing)
        self.orbit.dispose(); self.assertFalse(self.orbit.timer.isActive())
        self.window.language_picker.setCurrentIndex(1)
        self.assertEqual(self.orbit.toolbar.reset_action.text(),'Recentrer')

    def test_wheel_updates_are_coalesced_and_full_detail_returns(self):
        pivot=self.pivot()
        with patch.object(self.canvas,'draw_idle') as draw:
            for i in range(40): self.orbit.change_zoom(1.01)
            self.assertEqual(draw.call_count,0)
            self.assertTrue(self.orbit.previewing)
            self.orbit.flush(); self.assertEqual(draw.call_count,1)
        self.orbit.finish_zoom()
        self.assertFalse(self.orbit.previewing)
        self.assertFalse(self.orbit.settle.isActive())
        np.testing.assert_allclose(self.pivot(),pivot)

    def test_preview_works_for_every_3d_geometry_type(self):
        rng=np.random.default_rng(7)
        frame=pd.DataFrame(rng.uniform(0,10,(80,3)),columns=['X','Y','Z'])
        frame['V']=frame.X+frame.Y-frame.Z
        for mode in ('points','surface','tin','wireframe','slices','voxels'):
            result=compute('scene',frame,dict(x='X',y='Y',z='Z',value='V',mode=mode,resolution=12))
            self.page.display_result(result)
            controller=self.page.plots[0][1].canvas._stc_orbit
            controller.press(SimpleNamespace(button=1,inaxes=controller.ax,x=100,y=100))
            controller.motion(SimpleNamespace(x=120,y=115)); controller.flush(); controller.release()
            self.assertFalse(controller.previewing,mode)
            self.assertTrue(all(a.get_visible()==visible for a,visible in controller.artists),mode)

    def test_old_inverted_camera_is_bounded_and_controls_match_without_dirtying_project(self):
        self.result['options'].update(elevation=150,azimuth=480)
        self.window.dirty=False
        self.page.display_result(self.result)
        controller=self.page.plots[0][1].canvas._stc_orbit
        self.assertEqual(controller.ax.elev,89)
        self.assertEqual(self.page.fields['elevation'].value(),89)
        self.assertEqual(controller.ax.azim,120)
        self.assertFalse(self.window.dirty)
