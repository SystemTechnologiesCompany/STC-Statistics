import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from scipy import stats
from stc_statistics.science import (compute,grid_samples,idw,project_xy,pack_result,unpack_result,
    regression_metrics,render_result,notebook_code)
from stc_statistics.science_exports import export_ascii,export_obj,export_table

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


class SpatialTests(unittest.TestCase):
    def setUp(self):
        x,y=np.meshgrid(np.linspace(0,10,6),np.linspace(0,8,5))
        self.frame=pd.DataFrame({'X':x.ravel(),'Y':y.ravel(),'Z':2*x.ravel()+3*y.ravel()+7})
        self.options=dict(x='X',y='Y',z='Z',value='Z',resolution=16,interpolation='linear',mode='contour')

    def test_linear_grid_reproduces_a_plane_with_square_cells(self):
        result=compute('maps',self.frame,self.options)
        x,y=result['axes']; xx,yy=np.meshgrid(x,y); expected=2*xx+3*yy+7
        valid=np.isfinite(result['field'])
        np.testing.assert_allclose(result['field'][valid],expected[valid],atol=1e-10)
        np.testing.assert_allclose(np.diff(x),result['spacing'])
        np.testing.assert_allclose(np.diff(y),result['spacing'])

    def test_idw_exact_samples_and_constant_field(self):
        points=np.array([[0.,0.],[1,0],[0,1]])
        np.testing.assert_allclose(idw(points,np.array([2.,4,9]),points,3,2),[2,4,9])
        np.testing.assert_allclose(idw(points,np.ones(3)*5,np.array([[.2,.3],[.1,.1]])),5)

    def test_uncoloured_sample_map_accepts_collinear_positions_without_fake_grid(self):
        frame=pd.DataFrame({'X':[0.,1.,2.],'Y':[0.,2.,4.]})
        result=compute('maps',frame,{'x':'X','y':'Y','value':None,'mode':'samples'})
        self.assertNotIn('field',result)
        self.assertEqual(list(result['tables']['Sample values']),['X','Y'])
        self.assertEqual(len(render_result(result)),1)

    def test_unexaggerated_scene_preserves_coordinate_aspect(self):
        result=compute('scene',self.frame,dict(self.options,mode='surface',exaggeration=1))
        axes=render_result(result)[0][1].axes[0]
        actual=axes.get_box_aspect()
        expected=np.array([np.ptp(result['axes'][0]),np.ptp(result['axes'][1]),np.nanmax(result['field'])-np.nanmin(result['field'])])
        np.testing.assert_allclose(actual/actual[0],expected/expected[0],rtol=1e-10)

    def test_duplicate_coordinates_are_averaged_and_nonfinite_rows_excluded(self):
        frame=pd.DataFrame({'X':[0,0,1,0,np.nan],'Y':[0,0,0,1,2],'Z':[2,4,5,6,8]})
        result=grid_samples(frame,dict(self.options,interpolation='idw'))
        origin=np.all(result['points']==[0,0],axis=1)
        self.assertEqual(result['values'][origin][0],3)
        self.assertTrue(np.isnan(result['field'][-1,-1]))

    def test_collinear_samples_and_duplicate_roles_fail_clearly(self):
        frame=pd.DataFrame({'X':[0,1,2],'Y':[0,2,4],'Z':[1,3,8]})
        with self.assertRaises(ValueError): compute('maps',frame,self.options)
        with self.assertRaises(ValueError): compute('maps',self.frame,dict(self.options,y='X'))

    def test_regional_plane_residual_is_zero_for_exact_plane(self):
        result=compute('maps',self.frame,dict(self.options,mode='residual'))
        self.assertLess(np.nanmax(np.abs(result['field'])),1e-10)

    def test_gradient_matches_analytic_plane(self):
        result=compute('maps',self.frame,dict(self.options,mode='gradient'))
        np.testing.assert_allclose(result['field'][np.isfinite(result['field'])],np.sqrt(13),atol=1e-10)

    def test_wgs84_to_utm_known_meridian_and_hemisphere(self):
        points,label,epsg=project_xy(np.array([[3.,0.],[3.,45.]]),{'coordinate_mode':'wgs84','utm_zone':31})
        np.testing.assert_allclose(points[:,0],500000,atol=1e-7)
        self.assertAlmostEqual(points[0,1],0,places=7)
        self.assertAlmostEqual(points[1,1],4982950.400226552,places=2)
        self.assertEqual(epsg,32631)
        south,_,epsg=project_xy(np.array([[3.,-1.]]),{'coordinate_mode':'wgs84','utm_zone':31})
        self.assertGreater(south[0,1],9800000); self.assertEqual(epsg,32731)
        with self.assertRaises(ValueError): project_xy(np.array([[3.,90.]]),{'coordinate_mode':'wgs84'})
        with self.assertRaises(ValueError): project_xy(np.array([[3.,-1.],[3,1]]),{'coordinate_mode':'wgs84'})

    def test_profile_interpolates_the_same_map_units(self):
        result=compute('maps',self.frame,dict(self.options,profile=True,start_x=1,start_y=1,end_x=8,end_y=6))
        profile=result['tables']['Profile']
        np.testing.assert_allclose(profile.Value,2*profile.X+3*profile.Y+7,atol=1e-10)
        self.assertAlmostEqual(profile.Distance.iloc[-1],np.hypot(7,5))

    def test_scalar_volume_linear_reproduces_affine_property(self):
        points=np.array(np.meshgrid([0.,1.],[0.,1.],[0.,1.],indexing='ij')).reshape(3,-1).T
        frame=pd.DataFrame(points,columns=['X','Y','Z']); frame['V']=points@np.array([2.,3.,4.])+1
        options=dict(x='X',y='Y',z='Z',value='V',resolution=12,interpolation='linear',mode='slices')
        result=compute('scene',frame,options)
        x,y,z=np.meshgrid(*result['axes'],indexing='ij')
        np.testing.assert_allclose(result['field'],2*x+3*y+4*z+1,atol=1e-10)
        self.assertEqual(len(render_result(result)),1)

    def test_spatial_formats_have_real_cell_coordinates_and_finite_mesh_faces(self):
        result=compute('maps',self.frame,self.options)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'grid.asc'; export_ascii(result,path)
            lines=path.read_text().splitlines(); header=dict(line.split(maxsplit=1) for line in lines[:6])
            self.assertEqual(int(header['ncols']),len(result['axes'][0]))
            self.assertAlmostEqual(float(header['xllcorner']),result['axes'][0][0]-result['spacing']/2)
            stored=np.loadtxt(path,skiprows=6)
            original=result['field'][::-1]
            np.testing.assert_allclose(stored[np.isfinite(original)],original[np.isfinite(original)])
            scene=compute('scene',self.frame,dict(self.options,mode='tin'))
            mesh=Path(directory)/'surface.obj'; export_obj(scene,mesh)
            vertices=[l for l in mesh.read_text().splitlines() if l.startswith('v ')]
            faces=[l for l in mesh.read_text().splitlines() if l.startswith('f ')]
            self.assertEqual(len(vertices),len(scene['points'])); self.assertGreater(len(faces),0)
            self.assertNotIn('nan',mesh.read_text())


class RelationshipTests(unittest.TestCase):
    def test_negative_association_and_pair_counts_are_not_confused_with_r_squared(self):
        frame=pd.DataFrame({'A':[1,2,3,4,np.nan],'B':[8,6,4,2,1],'Constant':[7]*5})
        result=compute('relations',frame,{'columns':list(frame),'method':'pearson','mode':'heatmap'})
        self.assertAlmostEqual(result['correlation'].loc['A','B'],-1)
        self.assertEqual(result['counts'].loc['A','B'],4)
        self.assertTrue(np.isnan(result['correlation'].loc['Constant','Constant']))
        row=result['tables']['Bivariate statistics'].iloc[0]
        self.assertAlmostEqual(row['Squared coefficient'],1); self.assertAlmostEqual(row['OLS R²'],1)
        self.assertLess(row['OLS slope'],0)

    def test_spearman_ties_and_missing_data_match_scipy_pairwise(self):
        frame=pd.DataFrame({'A':[1,1,2,4,np.nan,8],'B':[2,3,np.nan,8,10,12],'C':[1,3,2,6,5,8]})
        result=compute('relations',frame,{'columns':list(frame),'method':'spearman','mode':'matrix'})
        pair=frame[['A','B']].dropna()
        self.assertAlmostEqual(result['correlation'].loc['A','B'],stats.spearmanr(pair.A,pair.B).statistic)
        q=result['tables']['Bivariate statistics']['q (BH)']
        self.assertTrue(q.between(0,1).all())

    def test_old_correlation_button_also_generates_a_heatmap(self):
        from stc_statistics.analysis import correlation_code
        for method in ('pearson','spearman'):
            code=correlation_code(method)
            self.assertIn('axis.imshow',code)
            self.assertIn('vmin=-1',code)
            self.assertIn('application/vnd.stc.table+json',code)


class PredictionTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(51)
        self.frame=pd.DataFrame(rng.normal(size=(80,3)),columns=['A','B','C'])
        self.frame['Target']=self.frame.A*3+self.frame.B**2+rng.normal(0,.1,80)
        self.frame['Well']=['Well-'+str(i%8) for i in range(80)]
        self.options={'features':['A','B','C'],'target':'Target','algorithm':'both','trees':15,'repeats':2,'seed':42}

    def test_metrics_are_exact_and_allow_negative_or_undefined_r2(self):
        metrics=regression_metrics([1,2,3],[1,3,2])
        self.assertAlmostEqual(metrics['RMSE'],np.sqrt(2/3))
        self.assertAlmostEqual(metrics['MAE'],2/3); self.assertAlmostEqual(metrics['R²'],0)
        self.assertLess(regression_metrics([1,2,3],[10,10,10])['R²'],0)
        self.assertTrue(np.isnan(regression_metrics([1,1,1],[1,1,1])['R²']))

    def test_rf_gb_share_repeated_splits_and_tables_match_predictions(self):
        first=compute('prediction',self.frame,self.options)
        second=compute('prediction',self.frame,self.options)
        pd.testing.assert_frame_equal(first['tables']['Train and test metrics'],second['tables']['Train and test metrics'])
        metrics=first['tables']['Train and test metrics']; predictions=first['tables']['Predictions']
        self.assertEqual(len(metrics),12)
        for repeat in (1,2):
            for subset in ('Train','Test'):
                a=predictions[(predictions.Model=='Random Forest')&(predictions.Repeat==repeat)&(predictions.Split==subset)]
                b=predictions[(predictions.Model=='Gradient Boosting')&(predictions.Repeat==repeat)&(predictions.Split==subset)]
                self.assertEqual(a['Row position (0-based)'].tolist(),b['Row position (0-based)'].tolist())
                expected=regression_metrics(a.Observed,a.Predicted)
                actual=metrics[(metrics.Model=='Random Forest')&(metrics.Repeat==repeat)&(metrics.Split==subset)].iloc[0]
                for key in expected: self.assertAlmostEqual(actual[key],expected[key])

    def test_tuning_does_not_see_held_out_response(self):
        options=dict(self.options,algorithm='rf',repeats=1,tune=True,trials=2,folds=2)
        first=compute('prediction',self.frame,options)
        prediction=first['tables']['Predictions']
        heldout=prediction[(prediction.Model=='Random Forest')&(prediction.Split=='Test')]['Row position (0-based)'].to_numpy()
        changed=self.frame.copy(); changed.loc[heldout,'Target']+=1000000
        second=compute('prediction',changed,options)
        train=lambda r:r['tables']['Predictions'].query("Model == 'Random Forest' and Split == 'Train'").Predicted.reset_index(drop=True)
        pd.testing.assert_series_equal(train(first),train(second))
        pd.testing.assert_frame_equal(first['tables']['Hyperparameters'],second['tables']['Hyperparameters'])

    def test_well_groups_are_separate_and_missing_responses_get_predictions(self):
        frame=self.frame.copy(); frame.loc[[0,1],'Target']=np.nan
        result=compute('prediction',frame,dict(self.options,split='group',group='Well',repeats=1))
        prediction=result['tables']['Predictions'].query("Model == 'Random Forest'")
        train=prediction.query("Split == 'Train'")['Row position (0-based)'].to_numpy()
        test=prediction.query("Split == 'Test'")['Row position (0-based)'].to_numpy()
        self.assertFalse(set(frame.iloc[train].Well)&set(frame.iloc[test].Well))
        self.assertEqual(len(prediction.query("Split == 'Unlabelled'")),2)

    def test_response_in_features_is_rejected(self):
        with self.assertRaises(ValueError): compute('prediction',self.frame,dict(self.options,features=['A','Target']))


class RecipeAndExportTests(unittest.TestCase):
    def test_volume_roundtrip_preserves_empty_surface_mesh_shape(self):
        rng=np.random.default_rng(13)
        frame=pd.DataFrame(rng.uniform(0,10,(45,3)),columns=['X','Y','Z'])
        frame['V']=frame.X+frame.Y+frame.Z
        for mode in ('slices','voxels'):
            result=compute('scene',frame,{'x':'X','y':'Y','z':'Z','value':'V','mode':mode,'resolution':12})
            restored=unpack_result(json.loads(json.dumps(pack_result(result),allow_nan=False)))
            self.assertEqual(restored['triangles'].shape,(0,3))
            np.testing.assert_allclose(restored['field'],result['field'],equal_nan=True)
            self.assertEqual(len(render_result(restored)),1)

    def test_geojson_points_and_ascii_grid_roundtrip(self):
        from stc_statistics.spatial_io import read_geojson,read_ascii_grid
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            geo=folder/'points.geojson'
            geo.write_text(json.dumps({'type':'FeatureCollection','features':[
                {'type':'Feature','geometry':{'type':'Point','coordinates':[3.1,31.2,140]},'properties':{'K':25,'Longitude':'keep-property'}}]}))
            frame=read_geojson(geo)
            self.assertAlmostEqual(frame.Longitude.iloc[0],3.1)
            self.assertEqual(frame.Property_Longitude.iloc[0],'keep-property')
            self.assertEqual(frame.K.iloc[0],25)
            grid=folder/'grid.asc'
            grid.write_text('ncols 2\nnrows 2\nxllcorner 100\nyllcorner 200\ncellsize 10\nNODATA_value -9999\n1 2\n3 -9999\n')
            values=read_ascii_grid(grid)
            self.assertEqual(values.X.tolist(),[105,115,105,115])
            self.assertEqual(values.Y.tolist(),[215,215,205,205])
            self.assertTrue(np.isnan(values.Value.iloc[-1]))

    def test_geojson_nonpoint_geometry_is_rejected_explicitly(self):
        from stc_statistics.spatial_io import read_geojson
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'polygon.geojson'
            path.write_text(json.dumps({'type':'Feature','geometry':{'type':'Polygon','coordinates':[]}}))
            with self.assertRaisesRegex(ValueError,'point features'):
                read_geojson(path)

    def test_json_roundtrip_restores_live_geometry_and_typed_values_without_pickle(self):
        frame=pd.DataFrame({'X':[0,1,0,1],'Y':[0,0,1,1],'Z':[1,2,3,4]})
        result=compute('scene',frame,{'x':'X','y':'Y','z':'Z','value':'Z','mode':'surface','resolution':12})
        payload=json.dumps(pack_result(result),allow_nan=False)
        restored=unpack_result(json.loads(payload))
        np.testing.assert_allclose(result['field'],restored['field'],equal_nan=True)
        pd.testing.assert_frame_equal(result['tables']['Grid values'],restored['tables']['Grid values'],check_dtype=False,atol=1e-12)
        self.assertEqual(len(render_result(restored)),1)

    def test_python_recipe_is_self_contained_and_computes_real_outputs(self):
        options={'columns':['A','B'],'mode':'heatmap','method':'pearson'}
        code=notebook_code('relations',options)
        code='\n'.join(line for line in code.splitlines() if not line.startswith('%'))
        namespace={'df':pd.DataFrame({'A':[1,2,3,4],'B':[3,6,9,12]})}
        with patch('IPython.display.display'),patch('builtins.print'):
            exec(compile(code,'recipe','exec'),namespace)
        self.assertAlmostEqual(namespace['result']['correlation'].loc['A','B'],1)
        self.assertNotIn('from .',code)

    def test_full_excel_export_keeps_numbers_and_formula_like_text_literal(self):
        import openpyxl
        frame=pd.DataFrame({'Number':[1.234567890123,2.0],'Text':['=1+1','@danger']})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'result.xlsx'; export_table(frame,path)
            book=openpyxl.load_workbook(path)
            self.assertAlmostEqual(book.active['B2'].value,frame.Number.iloc[0])
            self.assertEqual(book.active['C2'].data_type,'s')
            self.assertTrue(book.active['C2'].value.startswith("'="))
