import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLBACKEND','Agg')
import tempfile
import unittest
from pathlib import Path
import nbformat
import numpy as np
import pandas as pd
from scipy import stats
from stc_statistics.advanced import advanced_analysis, geology, recipe
from stc_statistics.projects import clean_frame, save_project, load_project


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(11)
        self.df=pd.DataFrame({'x':rng.normal(size=40),'z':rng.normal(size=40)})
        self.df['y']=2+3*self.df.x+.2*self.df.z+rng.normal(scale=.1,size=40)

    def test_regression_and_confidence_intervals(self):
        table,notes=advanced_analysis(self.df,'regression',['x','z','y'])
        self.assertAlmostEqual(table.loc['x','Coefficient'],3,delta=.1)
        self.assertLess(table.loc['x','CI lower'],table.loc['x','Coefficient'])
        self.assertIn('causality',notes)
        table,_=advanced_analysis(self.df,'ci',['x'])
        expected=stats.t.interval(.95,39,loc=self.df.x.mean(),scale=stats.sem(self.df.x))
        self.assertAlmostEqual(table.iloc[0,2],expected[0])

    def test_tests_match_scipy(self):
        for method,expected in [('welch',stats.ttest_ind(self.df.x,self.df.z,equal_var=False)),('paired',stats.ttest_rel(self.df.x,self.df.z)),('anova',stats.f_oneway(self.df.x,self.df.z)),('one_t',stats.ttest_1samp(self.df.x,0)),('normality',stats.shapiro(self.df.x))]:
            cols=['x','z'] if method in ('welch','paired','anova') else ['x']
            table,notes=advanced_analysis(self.df,method,cols,'fr')
            self.assertAlmostEqual(table['p-value'].iloc[0],expected.pvalue)
            self.assertIn('H0',notes)

    def test_pca_and_deterministic_clusters(self):
        table,notes=advanced_analysis(self.df,'pca',['x','z'])
        self.assertEqual(table.shape,(2,2))
        self.assertIn('Explained variance',notes)
        a,_=advanced_analysis(self.df,'cluster',['x','z'],clusters=3)
        b,_=advanced_analysis(self.df,'cluster',['x','z'],clusters=3)
        pd.testing.assert_frame_equal(a,b)
        with self.assertRaises(ValueError):
            advanced_analysis(self.df,'cluster',['x','z'],clusters=100)

    def test_cleaning_and_source_unchanged(self):
        frame=pd.DataFrame({'x':['1,5',None,'1,5','invalid']})
        cleaned=clean_frame(frame,['x'],'numeric')
        self.assertEqual(cleaned.x.iloc[0],1.5)
        self.assertEqual(cleaned.x.isna().sum(),2)
        filled=clean_frame(cleaned,['x'],'median')
        self.assertFalse(filled.isna().any().any())
        self.assertEqual(len(clean_frame(frame,['x'],'duplicates')),3)
        self.assertEqual(frame.x.iloc[0],'1,5')

    def test_project_round_trip_preserves_types_and_outputs(self):
        frame=pd.DataFrame({'n':pd.Series([1,None,9007199254740993],dtype='Int64'),'date':pd.to_datetime(['2020-01-01',None,'2020-02-01'])})
        notebook=nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell('print(42)',outputs=[nbformat.v4.new_output('stream',name='stdout',text='42\n')])])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'project.stcproj'
            save_project(path,frame,notebook,{'chart':{'bins':21}})
            actual,nb,settings=load_project(path)
            pd.testing.assert_frame_equal(frame,actual)
            self.assertEqual(nb.cells[0].outputs[0].text,'42\n')
            self.assertEqual(settings['chart']['bins'],21)

    def test_geology_units_depth_and_invalid_rows(self):
        import matplotlib.pyplot as plt
        frame=pd.DataFrame({'phi':[20,0,110],'k':[100,10,10]})
        table=geology(frame,'reservoir',['phi','k'])
        self.assertEqual(len(table),1)
        self.assertAlmostEqual(table.RQI_um.iloc[0],.0314*np.sqrt(100/.2))
        self.assertAlmostEqual(table.FZI_um.iloc[0],table.RQI_um.iloc[0]/.25)
        geology(pd.DataFrame({'log':[1,2,3],'depth':[20,10,30]}),'depth',['log','depth'])
        self.assertTrue(plt.gca().yaxis_inverted())
        plt.close('all')

    def test_generated_recipe_is_self_contained(self):
        code=recipe('ci',['x'],'en')
        ns={'df':self.df}
        exec(code,ns)
        self.assertEqual(len(ns['result']),1)

    def test_custom_charts_and_editable_full_table(self):
        import matplotlib.pyplot as plt
        from stc_statistics.plot_code import histogram_code,customize_code
        code=customize_code(histogram_code(),{'title':'Custom','bins':7,'color':'#123456','xscale':'linear','yscale':'linear'})
        exec(code,{'numeric':self.df[['x']],'plt':plt})
        self.assertEqual(len(plt.gca().patches),7)
        self.assertEqual(plt.gca().get_title(),'Custom')
        plt.close('all')
        from PySide6.QtWidgets import QApplication
        from stc_statistics.app import FrameModel
        qt=QApplication.instance() or QApplication([])
        model=FrameModel(pd.DataFrame({'x':[1.0]*1500}))
        self.assertEqual(model.rowCount(),1500)
        self.assertTrue(model.setData(model.index(1499,0),'2,5'))
        self.assertEqual(model.frame.iloc[-1,0],2.5)
        integer=FrameModel(pd.DataFrame({'x':[9007199254740993]}))
        self.assertTrue(integer.setData(integer.index(0,0),'9007199254740995'))
        self.assertEqual(integer.frame.iloc[0,0],9007199254740995)
        self.assertTrue(integer.setData(integer.index(0,0),''))
        self.assertTrue(pd.isna(integer.frame.iloc[0,0]))


if __name__=='__main__':
    unittest.main()
