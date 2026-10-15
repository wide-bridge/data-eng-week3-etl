# 3주차 Python ETL 실습

pandas로 주문 데이터를 탐색·변환·결합하고 DuckDB로 100만 행의 이벤트 데이터를 분석한 학습 기록입니다. 데이터는 고정 시드로 생성하는 합성 데이터입니다.

## 최종 제출물 (3-5)

- [품질 리포트](quality_report.md): 처리 근거, 전후 수치, 검증 결과와 한계
- [품질 CSV](quality_report.csv), [정제 데이터](orders_clean.parquet)
- [정제 스크립트](clean_orders.py), [검증 스크립트](verify_submission.py), [검증 결과](verification_results.json)
- [3-4 보완 실습 기록](실습기록_3-4.md)

검증 결과: 1,015 → 1,000행, 중복 15 → 0, 가격 결측 30 → 0, 카테고리 5 → 4.

### 제출물만 재현 (기존 실습 파일 없이)

가상환경과 requirements 설치 후 저장소 폴더에서 실행합니다. `make_orders.py`는 합성 원본을 생성하므로 실제 업무 데이터가 없는 실습용 복제본에서 실행하세요.

```bash
python make_orders.py
python clean_orders.py
python quality_report.py
python crosscheck.py
python verify_submission.py
```

### 3-4 누락 실습 실행

앞의 3-1~3-3 실행 순서로 입력 파일을 준비한 뒤 실행합니다. `events.parquet`는 `speed.py`로 생성합니다.

```bash
python sql_analysis.py
python roundtrip.py
```

`user_segments.parquet`(50,000행)와 `segment_summary.parquet`(3행)을 만듭니다. `sql_analysis.py`는 지역 집계·누적합·이동 평균·순위 비교를 검증합니다.

## 진행 범위

- 3-1: CSV 탐색, 결측·공백 확인, 파생 열 생성, Parquet 저장
- 3-2: 고객 마스터 결합, 중복 키 검증, 피벗과 재구조화
- 3-3: DuckDB SQL, CSV/Parquet 성능, 압축 및 파티션 비교
- 3-2 시계열·기초 통계와 미니 과제는 터미널에서 실행했습니다. 해당 코드는 현재 저장소에 별도 파일로 포함되지 않았습니다.
- 3-4: 파일 JOIN, SQL/Pandas 교차 검증, CTE·윈도 함수, 사용자 세그먼트 Parquet
- 3-5: 정제 파이프라인, 품질 리포트, 재실행·오류 주입·독립 재현 검증
- 3-4 누락 실습과 3-5 제출 정리는 AI 도움으로 보완하고 WSL에서 실행·검증했습니다.

## 실행 환경과 순서

Ubuntu/WSL, Python 3.12 환경에서 실습했습니다. 모든 명령은 이 저장소 폴더 안에서 실행합니다. 상대 경로는 실행한 현재 폴더를 기준으로 해석됩니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python make_orders.py
python explore.py
python transform.py
python make_customers.py
python analyze.py

python make_events.py
python query.py
python speed.py
```

`analyze.py`에는 재현을 위해 정상 결합 결과를 `orders_enriched.parquet`로 저장하는 코드를 추가했습니다. `speed.py`는 생성한 파일을 다시 쓰므로 실습 전용 폴더에서 실행하세요.

## 파일 안내

| 파일 | 역할 |
|---|---|
| `make_orders.py`, `make_customers.py` | 주문·고객 합성 데이터 생성 |
| `explore.py`, `transform.py`, `analyze.py` | 주문 탐색·변환·결합·집계 |
| `make_events.py` | 이벤트 1,000,000행 생성 |
| `query.py` | 파일 SQL 조회와 pandas 연동 |
| `speed.py` | 파일 크기·집계·열 선택·압축·파티션 비교 |
| `parted_again.py` | 기존 파티션 폴더에 다시 쓰는 의도적 실패 실습 |
| [실측기록_3-3.md](실측기록_3-3.md) | 2026-10-13 사용자 환경에서 측정한 결과 |

대용량 원본 CSV·이벤트 Parquet·가상환경은 Git에 포함하지 않습니다. 제출용 `orders_clean.parquet`, `quality_report.csv`와 3-4 결과 Parquet 두 개는 예외로 포함합니다. 원본은 생성 스크립트로 재생성합니다.

## 주요 측정 결과

CSV 40.6 MB → Parquet(zstd) 9.8 MB. 집계 질의는 이번 측정에서 약 34.9배 빨랐습니다. 시간과 배율은 환경·캐시·반올림에 따라 달라집니다. 코드의 MB 표시는 1024² 바이트 기준입니다.

`count(*)`는 Parquet 메타데이터로 최적화될 수 있어 전체 열 읽기 측정으로 사용할 수 없습니다. 다섯 열 집계는 읽는 열뿐 아니라 집계 연산도 달라지므로 순수 I/O만 비교한 수치는 아닙니다.

3-1~3-4 중간 데이터에는 금액 결측 30건과 의도적인 중복이 남아 있습니다. 3-5의 `orders_clean.parquet`에서는 결측과 중복을 처리했습니다. 금액의 `count`와 전체 행 수는 다릅니다.

파티션 비교에서는 `speed.py`가 파티션 파일에 `day` 열도 추가하므로 단일 파일과 스키마가 완전히 같지는 않습니다. 조회 결과가 같은지 확인하는 것이 우선입니다.

## 의도적 실패 실습

`speed.py`로 파티션을 만든 뒤 아래 명령을 실행하면, 기존 파일이 있는 폴더에 덮어쓰기 옵션 없이 쓰려고 하므로 오류가 발생하는 것이 예상 결과입니다.

```bash
python parted_again.py
```

## 학습 자료

[데이터 엔지니어링 과정 3주차](https://data-eng.jobability.co.kr/learning/week-3)의 실습 예제를 바탕으로 작성했습니다. 
