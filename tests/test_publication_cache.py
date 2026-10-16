import io
import json
from email.message import Message
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_site import build, load_report
import verify_publication as check


class Response(io.BytesIO):
    status = 200
    def __init__(self, data, headers):
        super().__init__(data)
        self.headers = Message()
        for key, value in headers.items():
            self.headers[key] = value


class PublicationCacheTests(unittest.TestCase):
    def test_existing_header_rules_do_not_conflict(self):
        text = (ROOT/'web/_headers').read_text()
        for name in check.JSON_FILES:
            check.validate_headers(check.configured_headers(text, '/'+name))
        with self.assertRaises(ValueError):
            check.validate_headers(check.configured_headers(text+'\n/*\n  Cache-Control: public\n', '/data.json'))

    def test_build_overwrites_old_json_and_keeps_data_schema(self):
        import ndx5s_daily as engine
        with tempfile.TemporaryDirectory() as folder, patch.object(engine, 'chartjs', return_value='// offline test asset'):
            out = Path(folder)/'dist'
            out.mkdir()
            (out/'data.json').write_text('{"date":"1900-01-01"}')
            (out/'qdii.json').write_text('{}')
            build(ROOT/'reports/latest.html', out, ROOT/'data/publication_policy.json')
            check.verify_artifact(out)
            result = json.loads((out/'data.json').read_text())
            self.assertEqual(result['date'], load_report(ROOT/'reports/latest.html')['date'])
            self.assertEqual((out/'qdii.json').read_bytes(), (ROOT/'data/qdii.json').read_bytes())
            (out/'data.json').write_text('{"date":"1900-01-01"}')
            with self.assertRaises(ValueError):
                check.verify_artifact(out)

    def test_failed_build_cannot_replace_previous_artifact(self):
        import ndx5s_daily as engine
        with tempfile.TemporaryDirectory() as folder, patch.object(engine, 'chartjs', side_effect=RuntimeError('asset unavailable')):
            out = Path(folder)/'dist'
            out.mkdir()
            (out/'data.json').write_text('previous successful artifact')
            with self.assertRaises(RuntimeError):
                build(ROOT/'reports/latest.html', out, ROOT/'data/publication_policy.json')
            self.assertEqual((out/'data.json').read_text(), 'previous successful artifact')

    def test_cached_or_weak_headers_are_rejected(self):
        good = check.REQUIRED_HEADERS
        for bad in ({**good, 'cache-control':'no-cache'}, {**good, 'age':'30'}, {**good, 'cf-cache-status':'HIT'}):
            with self.assertRaises(ValueError):
                check.validate_headers(bad)

    def test_two_remote_requests_compare_full_bytes_and_cache_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            bodies = {'data.json':json.dumps({'date':load_report(ROOT/'reports/latest.html')['date']}).encode(),
                      'qdii.json':(ROOT/'data/qdii.json').read_bytes()}
            for name, raw in bodies.items():
                (out/name).write_bytes(raw)
            def respond(request, **kwargs):
                self.assertNotIn('?', request.full_url)
                self.assertNotIn('Cache-control', request.headers)
                return Response(bodies[request.full_url.rsplit('/', 1)[-1]], check.REQUIRED_HEADERS)
            with patch.object(check.urllib.request, 'urlopen', side_effect=respond) as fetch, patch.object(check.time, 'sleep'):
                result = check.verify_remote('https://ndx5s.pages.dev', out)
                self.assertEqual(fetch.call_count, 4)
                self.assertEqual(result['data.json'][0]['sha256'], result['data.json'][1]['sha256'])
            with patch.object(check.urllib.request, 'urlopen', side_effect=lambda *a, **k:Response(b'{}', check.REQUIRED_HEADERS)):
                with self.assertRaises(ValueError):
                    check.verify_remote('https://ndx5s.pages.dev', out)
