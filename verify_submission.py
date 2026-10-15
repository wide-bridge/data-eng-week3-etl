"""제출 검증: 교차 검증, 재실행, 오류 주입, 실패 시 저장 차단, 독립 재현."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

import duckdb
import pandas as pd
from clean_orders import clean, load_raw, validate


def main():
    source_hash = hashlib.sha256(Path('orders.csv').read_bytes()).hexdigest()
    raw = load_raw()
    first, second = clean(raw), clean(load_raw())
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first, clean(first))
    assert not any(validate(first).values())
    saved = pd.read_parquet('orders_clean.parquet')
    pd.testing.assert_frame_equal(first.reset_index(drop=True), saved.reset_index(drop=True))
    cross = duckdb.sql("""
        SELECT count(*) AS rows, count(*)-count(price) AS null_price,
          count(*)-count(DISTINCT order_id) AS dup_order_id,
          count(DISTINCT category) AS category_values,
          min(order_date) AS first_date, max(order_date) AS last_date
        FROM 'orders_clean.parquet'
    """).df().iloc[0]
    assert [int(cross[k]) for k in ['rows','null_price','dup_order_id','category_values']] == [1000,0,0,4]
    report = pd.read_csv('quality_report.csv').set_index('dataset')
    assert report.loc['before', ['rows','dup_order_id','null_price','category_values']].tolist() == [1015,15,30,5]
    assert report.loc['after', ['rows','dup_order_id','null_price','category_values']].tolist() == [1000,0,0,4]
    assert int(raw['category'].ne(raw['category'].str.strip()).sum()) == 20
    cases = {
        'price_le_0': ('price', -1000), 'quantity_le_0': ('quantity', 0),
        'quantity_gt_5': ('quantity', 6), 'unknown_cat': ('category', '알수없음'),
        'null_price': ('price', float('nan')), 'invalid_date': ('order_date', pd.NaT),
        'future_date': ('order_date', pd.Timestamp.today() + pd.Timedelta(days=2)),
    }
    for key, (column, value) in cases.items():
        bad = first.copy()
        bad.loc[bad.index[0], column] = value
        assert validate(bad)[key] == 1, key
    duplicate = pd.concat([first, first.head(1)], ignore_index=True)
    assert validate(duplicate)['dup_order_id'] == 1
    script = Path('clean_orders.py').resolve()
    with tempfile.TemporaryDirectory(prefix='week3-verify-') as folder:
        target = Path(folder)
        shutil.copy2(script, target / script.name)
        shutil.copy2('orders.csv', target / 'orders.csv')
        for _ in range(2):
            subprocess.run([sys.executable, script.name], cwd=target, check=True, capture_output=True, text=True)
            pd.testing.assert_frame_equal(saved, pd.read_parquet(target / 'orders_clean.parquet'))
        # 정상 산출물은 유지하고 잘못된 입력의 저장을 차단하는지 확인.
        old_output = (target / 'orders_clean.parquet').read_bytes()
        bad_raw = pd.read_csv(target / 'orders.csv')
        bad_raw.loc[0, 'price'] = -1000
        bad_raw.to_csv(target / 'orders.csv', index=False)
        failed = subprocess.run([sys.executable, script.name], cwd=target, capture_output=True, text=True)
        assert failed.returncode == 1, failed.stdout + failed.stderr
        assert (target / 'orders_clean.parquet').read_bytes() == old_output
    assert hashlib.sha256(Path('orders.csv').read_bytes()).hexdigest() == source_hash
    result = {
        'status': 'PASS', 'raw_sha256': source_hash,
        'before': report.loc['before'].to_dict(), 'after': report.loc['after'].to_dict(),
        'median_after_dedup': float(raw.drop_duplicates('order_id')['price'].median()),
        'median_before_dedup': float(raw['price'].median()),
        'first_date': str(cross['first_date']), 'last_date': str(cross['last_date']),
        'checks': ['same_input_rerun', 'clean_idempotence', 'parquet_roundtrip',
                   'duckdb_pandas_crosscheck', 'invalid_value_detection',
                   'failure_exit_1_preserves_output', 'isolated_reproduction', 'raw_unchanged'],
    }
    Path('verification_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
