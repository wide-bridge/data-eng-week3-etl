# parted_again.py — 일부러 실패: OVERWRITE_OR_IGNORE 를 빼고 같은 폴더에 다시 씁니다
import duckdb

duckdb.sql("""
    COPY (SELECT * FROM 'events.csv')
    TO 'events_parted'
    (FORMAT parquet, PARTITION_BY (event_type), COMPRESSION zstd)
""")

