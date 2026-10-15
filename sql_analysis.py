"""3-4: 파일 JOIN, 교차 검증, CTE와 윈도 함수."""
import duckdb
import pandas as pd


def main():
    print('1. 구매 지출 상위 5명')
    print(duckdb.sql("""
        SELECT user_id, count(*) AS buys, sum(value) AS spend
        FROM 'events.parquet' WHERE event_type = 'buy'
        GROUP BY user_id ORDER BY spend DESC, user_id LIMIT 5
    """))
    sql_result = duckdb.sql("""
        SELECT c.region, count(*) AS orders,
               sum(o.price * o.quantity) AS total
        FROM 'orders_step1.parquet' o
        JOIN 'customers.csv' c ON o.customer_id = c.customer_id
        GROUP BY c.region ORDER BY c.region
    """).df()
    enriched = pd.read_parquet('orders_enriched.parquet')
    pd_result = (enriched.groupby('region')
                 .agg(orders=('order_id', 'count'), total=('amount', 'sum'))
                 .reset_index().sort_values('region').reset_index(drop=True))
    pd.testing.assert_frame_equal(sql_result, pd_result, check_dtype=False)
    assert sql_result['orders'].sum() == len(enriched)
    print('2-3. 지역 집계: SQL/Pandas 일치\n', sql_result)

    daily_sql = """
        SELECT date_trunc('day', ts) AS d, sum(value) AS revenue
        FROM 'events.parquet' WHERE event_type = 'buy' GROUP BY d
    """
    daily = duckdb.sql(f"""
        WITH daily AS ({daily_sql})
        SELECT d, revenue, sum(revenue) OVER (ORDER BY d) AS cum_revenue,
               avg(revenue) OVER (
                 ORDER BY d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7
        FROM daily ORDER BY d
    """).df()
    pd.testing.assert_series_equal(daily['cum_revenue'], daily['revenue'].cumsum(),
                                   check_names=False, check_dtype=False)
    pd.testing.assert_series_equal(daily['ma7'], daily['revenue'].rolling(7, min_periods=1).mean(),
                                   check_names=False, check_dtype=False)
    print('4. CTE 원본\n', duckdb.sql(daily_sql + ' ORDER BY d LIMIT 3'))
    print('4,6. 누적 매출 및 최근 7행 평균\n', daily.head(10))

    try:
        duckdb.sql("""SELECT customer_id, rank() OVER (ORDER BY price DESC) AS rnk
                      FROM 'orders_step1.parquet' WHERE rnk <= 3""").fetchall()
    except duckdb.BinderException:
        print('5. 예상 오류 확인: WHERE에서는 윈도 함수 결과를 필터링할 수 없음')
    else:
        raise AssertionError('예상한 BinderException이 발생하지 않음')
    customer_sql = """
        SELECT c.region, o.customer_id, sum(o.price * o.quantity) AS total
        FROM 'orders_step1.parquet' o JOIN 'customers.csv' c
        ON o.customer_id = c.customer_id GROUP BY c.region, o.customer_id
    """
    qualify = duckdb.sql(f"""
        WITH by_customer AS ({customer_sql})
        SELECT *, rank() OVER (PARTITION BY region ORDER BY total DESC) AS rnk
        FROM by_customer QUALIFY rnk <= 3 ORDER BY region, rnk, customer_id
    """).df()
    cte = duckdb.sql(f"""
        WITH by_customer AS ({customer_sql}), ranked AS (
          SELECT *, rank() OVER (PARTITION BY region ORDER BY total DESC) AS rnk
          FROM by_customer)
        SELECT * FROM ranked WHERE rnk <= 3 ORDER BY region, rnk, customer_id
    """).df()
    pd.testing.assert_frame_equal(qualify, cte)
    print('5. 지역별 상위 고객: QUALIFY/CTE 일치\n', qualify)
    print('7. DuckDB 편의 문법')
    print(duckdb.sql("SELECT category, sum(amount) AS total FROM 'orders_step1.parquet' GROUP BY ALL ORDER BY category"))
    print(duckdb.sql("SELECT * EXCLUDE (amount) FROM 'orders_step1.parquet' LIMIT 2"))
    print(duckdb.sql("SELECT DISTINCT ON (customer_id) customer_id, order_date, order_id FROM 'orders_step1.parquet' ORDER BY customer_id, order_date DESC, order_id DESC LIMIT 5"))
    print('3-4 SQL 분석 검증 PASS')


if __name__ == '__main__':
    main()
