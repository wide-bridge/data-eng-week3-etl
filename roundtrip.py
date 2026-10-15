"""3-4: DuckDB -> Pandas -> DuckDB -> Parquet."""
import duckdb
import pandas as pd


def main():
    top = duckdb.sql("""
        SELECT user_id, sum(value) AS spend FROM 'events.parquet'
        WHERE event_type = 'buy' GROUP BY user_id
        ORDER BY spend DESC, user_id LIMIT 100
    """).df()
    top['grade'] = pd.cut(top['spend'], [0, 15000, 25000, float('inf')], labels=['B', 'A', 'S'])
    print('고정 경계 등급\n', top['grade'].value_counts())
    q = top['spend'].quantile([0.33, 0.66]).tolist()
    top['grade2'] = pd.cut(top['spend'], [0, *q, float('inf')], labels=['B', 'A', 'S'])
    print('분위수 경계:', q)
    grade_summary = duckdb.sql("""
        SELECT grade2 AS grade, count(*) AS users, avg(spend) AS avg_spend
        FROM top GROUP BY grade2 ORDER BY avg_spend DESC
    """).df()
    assert grade_summary['users'].sum() == len(top) == 100
    print(grade_summary)
    users = duckdb.sql("""
        SELECT user_id,
          count(*) FILTER (WHERE event_type = 'view') AS views,
          count(*) FILTER (WHERE event_type = 'cart') AS carts,
          count(*) FILTER (WHERE event_type = 'buy') AS buys,
          sum(value) FILTER (WHERE event_type = 'buy') AS spend
        FROM 'events.parquet' GROUP BY user_id ORDER BY user_id
    """).df()
    # 조회 0건의 비율은 계산 불가. 수업 예제에서는 0으로 분류하며 별도 건수를 표시한다.
    zero_views = int((users['views'] == 0).sum())
    users['cvr'] = (users['buys'] / users['views'].where(users['views'] != 0)).fillna(0).round(3)
    users['segment'] = 'normal'
    users.loc[users['cvr'] >= 0.1, 'segment'] = 'high_intent'
    users.loc[users['buys'] == 0, 'segment'] = 'browser'
    seg = duckdb.sql("""
        SELECT segment, count(*) AS users, round(avg(cvr), 3) AS avg_cvr,
               round(avg(coalesce(spend, 0))) AS avg_spend
        FROM users GROUP BY segment ORDER BY users DESC
    """).df()
    expected = users.groupby('segment').size().to_dict()
    assert seg.set_index('segment')['users'].to_dict() == expected
    assert users['user_id'].is_unique and seg['users'].sum() == len(users)
    users.to_parquet('user_segments.parquet', index=False)
    duckdb.sql("COPY (SELECT * FROM seg) TO 'segment_summary.parquet' (FORMAT parquet)")
    pd.testing.assert_frame_equal(users, pd.read_parquet('user_segments.parquet'))
    pd.testing.assert_frame_equal(seg, pd.read_parquet('segment_summary.parquet'))
    print('조회 0건 사용자:', zero_views)
    print('사용자 데이터:', users.shape)
    print(seg)
    print('3-4 왕복 및 저장 검증 PASS')


if __name__ == '__main__':
    main()
