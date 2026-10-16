#!/usr/bin/env python3
"""Check publication freshness and real HTTP cache headers without changing data."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE_CONTROL = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
REQUIRED_HEADERS = {'cache-control': CACHE_CONTROL, 'pragma': 'no-cache', 'expires': '0'}
JSON_FILES = ('data.json', 'qdii.json')


def validate_headers(headers):
    for key, value in REQUIRED_HEADERS.items():
        if headers.get(key) != value:
            raise ValueError(f'{key} 应为 {value!r}，实际为 {headers.get(key)!r}')
    if str(headers.get('cf-cache-status', '')).upper() in ('HIT', 'STALE', 'UPDATING', 'REVALIDATED'):
        raise ValueError('JSON 命中旧缓存')
    if int(headers.get('age') or '0') > 0:
        raise ValueError('JSON 返回了具有 Age 的缓存响应')


def configured_headers(text, path):
    """Include all matching blocks so duplicate/conflicting rules fail validation."""
    result = {}
    pattern = None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line[0].isspace():
            pattern = line.strip()
        elif pattern and fnmatch.fnmatchcase(path, pattern):
            key, value = line.strip().split(':', 1)
            key, value = key.lower(), value.strip()
            result[key] = result[key] + ', ' + value if key in result else value
    return result


def verify_artifact(output):
    from build_site import load_report, public_data, spx_data
    output = Path(output)
    report = load_report(ROOT/'reports/latest.html')
    policy = json.loads((ROOT/'data/publication_policy.json').read_text())
    expected = public_data(report, policy)
    if expected['modules'][2]['available'] and policy.get('mode') == 'operator_directed':
        expected['spx'] = spx_data(ROOT/'data/spx_close.json', report['dates'])
    actual = json.loads((output/'data.json').read_text())
    # Build time differs between invocations; every financial field must be identical.
    if {k:v for k,v in actual.items() if k != 'updated_at'} != {k:v for k,v in expected.items() if k != 'updated_at'}:
        raise ValueError('部署目录 data.json 不等于当前报告，禁止部署旧数据')
    if (output/'qdii.json').read_bytes() != (ROOT/'data/qdii.json').read_bytes():
        raise ValueError('部署目录 qdii.json 不等于最新成功快照')
    text = (output/'_headers').read_text()
    for name in JSON_FILES:
        validate_headers(configured_headers(text, '/'+name))
    print('本地发布检查通过：日报 '+actual['date']+'，QDII 内容及禁止缓存策略一致')


def verify_remote(base_url, output):
    results = {name:[] for name in JSON_FILES}
    # No query-string cache buster or request Cache-Control: test ordinary public URLs.
    for round_number in (1, 2):
        for name in JSON_FILES:
            request = urllib.request.Request(base_url.rstrip('/')+'/'+name, headers={
                'Accept': 'application/json', 'Accept-Encoding': 'identity',
                'User-Agent': 'NDX5S-publication-check/1.0', 'Connection': 'close'})
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError(f'{name} HTTP {response.status}，必须返回完整数据')
                raw = response.read()
                headers = {k.lower():v for k,v in response.headers.items()}
            validate_headers(headers)
            parsed = json.loads(raw)
            expected = (Path(output)/name).read_bytes()
            if raw != expected:
                raise ValueError(f'{name} 线上内容与本次部署文件不一致；线上日期 {parsed.get("date")}')
            result = dict(request=round_number, date=parsed.get('date'),
                          fetched_at=parsed.get('fetched_at'), sha256=hashlib.sha256(raw).hexdigest(),
                          headers={k:headers.get(k) for k in (*REQUIRED_HEADERS, 'age', 'cf-cache-status', 'cf-ray')})
            results[name].append(result)
            print(name, json.dumps(result, ensure_ascii=False))
        if round_number == 1:
            time.sleep(1)
    for name, responses in results.items():
        if responses[0]['sha256'] != responses[1]['sha256']:
            raise ValueError(name+' 两次独立响应内容不一致')
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'dist')
    parser.add_argument('--url')
    parser.add_argument('--attempts', type=int, default=1)
    args = parser.parse_args()
    verify_artifact(args.out)
    if args.url:
        for attempt in range(max(1, args.attempts)):
            try:
                verify_remote(args.url, args.out)
                break
            except Exception as error:
                if attempt + 1 >= args.attempts:
                    raise
                print('等待部署传播后重试：', error)
                time.sleep(5)


if __name__ == '__main__':
    main()
