import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_site import spx_data
class SPXTests(unittest.TestCase):
    def test_dates_align_without_filling_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'spx.json';p.write_text(json.dumps({'values':[{'date':'2026-10-09','close':1.0}]}))
            self.assertEqual(spx_data(p,['2026-10-08','2026-10-09']),[None,1.0])
            self.assertEqual(spx_data(p,['2026-10-12']),[None])
    def test_invalid_price_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'spx.json';p.write_text(json.dumps({'values':[{'date':'2026-10-09','close':-1.0}]}))
            with self.assertRaises(ValueError):spx_data(p,['2026-10-09'])
