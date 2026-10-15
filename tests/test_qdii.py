import copy,datetime as dt,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import update_qdii as q

def fixture(value='10.0',label='10元',duplicate=False):
    code='019736' if duplicate else '019737'
    return f'''<h1>QDII基金</h1><p>今日可申购总额度：{float(value):g}元</p><table id="fundTable"><tbody><tr><td><a href="/f/019736.html"><div>宝盈纳斯达克100指数A<span>A类</span></div></a></td><td data-value="{value}">{label}</td></tr></tbody></table><section><h2>暂停申购</h2><table><tbody><tr><td><a href="/f/{code}.html"><div>宝盈纳斯达克100指数C<span>C类</span></div></a></td></tr></tbody></table></section><p>数据更新：2小时前</p>'''

class QDIITests(unittest.TestCase):
    def test_zero_open_is_unlimited_and_paused_is_separate(self):
        d=q.parse_homepage(fixture('0','0元'))
        self.assertEqual([r['status'] for r in d['funds']],['unlimited','paused'])
        self.assertTrue(all(r['limit_yuan'] is None for r in d['funds']))
    def test_reject_duplicate_code_and_amount_mismatch(self):
        for s in [fixture(duplicate=True),fixture('10','5元'),fixture('0','50元'),fixture().replace('总额度：10元','总额度：20元')]:
            with self.assertRaises(ValueError):q.parse_homepage(s)
    def test_reject_missing_sections(self):
        with self.assertRaises(ValueError):q.parse_homepage('<h1>维护中</h1>')
    def test_merge_preserves_mixed_share_status_and_amounts(self):
        d=q.parse_homepage(fixture());g=q.group_funds(d['funds'],[dict(id='019736',name='宝盈纳斯达克100',index='ndx',codes=['019736','019737'])])
        self.assertEqual(len(g),1);self.assertEqual(g[0]['shares'],d['funds'])
    def test_first_baseline_is_not_a_change_and_later_change_is_recorded(self):
        d=q.parse_homepage(fixture());first=q.make_snapshot(d,[])
        self.assertEqual(first['changes'],[])
        second=q.make_snapshot(q.parse_homepage(fixture('5','5元')),[],first)
        self.assertEqual(len(second['changes']),1);self.assertEqual(second['changes'][0]['previous_limit_yuan'],10)
        q.validate_snapshot(second)
        invalid=copy.deepcopy(second);invalid['groups'][0]['shares']=[]
        with self.assertRaises(ValueError):q.validate_snapshot(invalid)
    def test_missing_previous_fund_rejected(self):
        d=q.parse_homepage(fixture());first=q.make_snapshot(d,[]);d['funds'].pop()
        with self.assertRaises(ValueError):q.make_snapshot(d,[],first)
    def test_failed_fetch_preserves_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();p=root/'data/qdii.json';p.write_text('unchanged')
            with patch.object(q,'ROOT',root),patch.object(q,'fetch_snapshot',side_effect=ValueError('test failure')),patch.object(sys,'argv',['update_qdii.py','--force']):
                with self.assertRaises(ValueError):q.main()
            self.assertEqual(p.read_text(),'unchanged');self.assertFalse(json.loads((root/'data/qdii_status.json').read_text())['success'])
    def test_all_hours_are_eligible_including_former_quiet_window(self):
        for hour in range(24):
            for minute in (0,29,30,37,59):
                self.assertTrue(q.eligible(dt.datetime(2026,10,12,hour,minute,tzinfo=q.TZ)))
    def test_real_snapshot_matches_mapping_and_summary(self):
        d=json.loads((ROOT/'data/qdii.json').read_text());q.validate_snapshot(d)
        groups=q.group_funds(d['funds'],json.loads((ROOT/'data/qdii_groups.json').read_text()))
        self.assertEqual(groups,d['groups']);self.assertEqual(sum(len(g['shares']) for g in groups),d['share_count'])
