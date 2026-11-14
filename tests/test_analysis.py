import unittest

import numpy as np
import pandas as pd

from stc_statistics.analysis import METRICS, analysis_code, conversion_code, summarize


class AnalysisTests(unittest.TestCase):
    def test_known_sample_and_missing(self):
        frame = pd.DataFrame({'a': [1, 2, 2, 3, np.nan, np.inf]})
        result = summarize(frame, ['a'])['a']
        self.assertEqual(result.iloc[0], 4)
        self.assertEqual(result.iloc[1], 2)
        self.assertEqual(result.iloc[2], 2)
        self.assertEqual(result.iloc[3], 2)
        self.assertEqual(result.iloc[4], '2.0')
        self.assertAlmostEqual(result.iloc[8], 2 / 3)
        self.assertAlmostEqual(result.iloc[9], np.sqrt(2 / 3))
        self.assertEqual(result.iloc[10], 1.75)
        self.assertEqual(result.iloc[11], 2.25)

    def test_empty_single_and_text(self):
        frame = pd.DataFrame({'empty': [np.nan, np.nan], 'single': [5.0, np.nan], 'text': ['a', 'b']})
        result = summarize(frame, list(frame.columns))
        self.assertNotIn('text', result)
        self.assertTrue(pd.isna(result['empty'].iloc[2]))
        self.assertTrue(pd.isna(result['empty'].iloc[13]))
        self.assertTrue(pd.isna(result['single'].iloc[8]))
        self.assertEqual(result['single'].iloc[2], 5)
        with self.assertRaises(ValueError):
            summarize(frame, ['text'])

    def test_generated_code_matches_calculation_both_languages(self):
        frame = pd.DataFrame({'A': [1, 3, 8, 9], 'B': [10, 20, 30, 40]})
        for language in ['en', 'fr']:
            namespace = {'df': frame}
            exec(analysis_code(['A', 'B'], language), namespace)
            expected = summarize(frame, ['A', 'B'])
            expected.index = METRICS[language]
            pd.testing.assert_frame_equal(namespace['summary'], expected)

    def test_decimal_comma_and_invalid_values(self):
        namespace = {'df': pd.DataFrame({'x': ['12,5', '1\u00a0234,5', 'bad', None]}), 'pd': pd}
        exec(conversion_code(['x'], True), namespace)
        values = namespace['df']['x']
        self.assertEqual(values.iloc[0], 12.5)
        self.assertEqual(values.iloc[1], 1234.5)
        self.assertTrue(pd.isna(values.iloc[2]))
        self.assertTrue(pd.isna(values.iloc[3]))

    def test_excel_roundtrip(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.xlsx'
            frame = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 8, 12]})
            with pd.ExcelWriter(path) as writer:
                frame.to_excel(writer, sheet_name='Sheet A', index=False)
                frame[['b']].to_excel(writer, sheet_name='Sheet B', index=False)
            with pd.ExcelFile(path) as workbook:
                self.assertEqual(workbook.sheet_names, ['Sheet A', 'Sheet B'])
            pd.testing.assert_frame_equal(pd.read_excel(path, sheet_name='Sheet A'), frame)


if __name__ == '__main__':
    unittest.main()
