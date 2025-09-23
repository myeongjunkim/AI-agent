# DART MCP Server

한국 금융감독원 DART (Data Analysis, Retrieval and Transfer System) API를 위한 MCP (Model Context Protocol) 서버입니다.

## 주요 기능

### 🔍 심층 검색 파이프라인
- **자연어 쿼리 처리**: "최근 3개월 메리츠금융의 주식매수선택권 자료" 같은 자연어로 검색
- **지능형 쿼리 확장**: LangExtract를 통한 날짜, 기업명, 문서유형 자동 추출
- **기업명 퍼지 매칭**: 부정확한 기업명도 자동으로 정확한 기업명으로 변환
- **문서 내용 자동 가져오기**: 검색된 공시의 실제 내용을 자동으로 추출
- **종합 답변 생성**: LLM을 활용한 검색 결과 종합 분석 및 답변

### 📊 기본 API 기능
- **공시정보 조회**: 기업별 공시 목록 검색 및 조회
- **공시서류 조회**: 공시 원문 및 첨부 문서 조회
- **재무정보 조회**: 재무제표 및 XBRL 데이터 조회
- **사업보고서 조회**: 배당, 임원, 주식 등 항목별 데이터 조회
- **지분공시 조회**: 주요 주주 현황 및 변동 조회
- **주요사항/증권신고서**: 합병, 증자 등 주요 이벤트 조회
- **URL 파싱**: DART 웹페이지 내용 직접 파싱

## 설치

### 1. 패키지 설치

```bash
cd dart-mcp
pip install -e .
```

또는 uv 사용:

```bash
cd dart-mcp
uv pip install -e .
```

### 2. 환경 설정

`.env` 파일을 생성하고 DART API 키를 설정합니다:

```env
DART_API_KEY=your-dart-api-key-here
```

DART API 키는 [DART OpenAPI](https://opendart.fss.or.kr/) 에서 발급받을 수 있습니다.

## API 사용 예시

### 🔥 심층 검색 (권장)

```python
from workflow.dart_orchestrator import DartOrchestrator
from tools import dart_api_tools

# 오케스트레이터 초기화
orchestrator = DartOrchestrator(dart_api_tools)

# 자연어로 검색 실행
result = await orchestrator.search_pipeline(
    query="최근 3개월 삼성전자 자사주 매입 현황",
    max_attempts=3,
    max_results_per_search=30
)

# 또는 MCP 도구로 직접 사용
await dart_deep_search(
    "2024년 3분기 실적 발표 기업들"
)
```

### 기업 정보 조회

```python
# 기업명으로 검색 (퍼지 매칭 지원)
search_companies_by_name("삼성")

# 특정 기업 정보 조회
get_company_info("삼성전자")
get_company_info("005930")  # 종목코드 사용
```

### 공시 목록 조회

```python
# 특정 기업의 공시
search_company_disclosures(
    company="삼성전자",
    start_date="2024-01-01",
    end_date="2024-12-31",
    pblntf_detail_ty="A001"  # 사업보고서
)
```

### 재무제표 조회

```python
# 단일 기업
get_financial_statements(
    company="005930",
    year=2023,
    report_code="11011"  # 사업보고서
)

# 여러 기업 동시 조회
get_financial_statements(
    company="005930,000660,005380",
    year=2023
)
```

### 사업보고서 항목 조회

```python
# 배당 정보
get_business_report_data(
    company="삼성전자",
    business_report_type="배당",
    year=2023
)

# 임원 정보
get_business_report_data(
    company="005930",
    business_report_type="임원",
    year=2023
)
```

### 주주 현황 조회

```python
# 대량보유상황보고
get_major_shareholders(
    company="삼성전자",
    shareholder_type="major"
)
```

### URL 파싱

```python
# DART 웹페이지 파싱
parse_dart_url_content(
    "http://dart.fss.or.kr/report/viewer.do?rcpNo=20240308000798"
)

# 여러 URL 동시 파싱
parse_multiple_dart_urls(
    "url1,url2,url3"
)
```

## 도구 목록

### 🔍 심층 검색 도구
- `dart_deep_search`: 자연어 쿼리를 통한 지능형 DART 검색

### 📋 공시정보 관련
- `search_company_disclosures`: 공시 목록 검색
- `get_company_info`: 기업 정보 조회
- `search_companies_by_name`: 기업명 검색
- `find_corporation_code`: 기업 고유번호 조회

### 📄 공시서류 관련
- `get_document_content`: 공시 원문 조회
- `get_attached_documents`: 첨부 문서 조회

### 💰 재무정보 관련
- `get_financial_statements`: 재무제표 조회
- `get_xbrl_taxonomy`: XBRL 표준계정과목 조회

### 📈 사업보고서 관련
- `get_business_report_data`: 사업보고서 항목별 데이터

### 👥 지분공시 관련
- `get_major_shareholders`: 주요 주주 현황

### 🔄 주요사항/증권신고서
- `get_major_events`: 주요사항보고서 
- `get_securities_report`: 증권신고서

### 🔗 URL 파싱
- `parse_dart_url_content`: 단일 URL 파싱
- `parse_multiple_dart_urls`: 다중 URL 파싱
- `extract_structured_info_from_documents`: 구조화된 정보 추출

### ⚙️ 옵션 조회
- `get_available_options`: 사용 가능한 옵션 목록

## 리소스

MCP 리소스를 통해 설정 정보를 확인할 수 있습니다:

- `dart://api/status`: API 연결 상태
- `dart://options/all`: 모든 옵션 정보

## 프로젝트 구조

```
dart-mcp/
├── workflow/               # 심층 검색 파이프라인
│   ├── dart_orchestrator.py    # 메인 오케스트레이터
│   └── utils/
│       ├── query_expander.py       # 쿼리 확장
│       ├── query_parser_langextract.py  # LangExtract 파서
│       ├── document_fetcher.py     # 문서 내용 가져오기
│       ├── sufficiency_checker.py  # 충분성 검사
│       └── synthesizer.py          # 답변 생성
├── utils/                  # 공통 유틸리티
│   ├── company_validator.py    # 기업명 검증 (퍼지 매칭)
│   ├── date_parser.py          # 날짜 파싱
│   ├── content_cleaner.py      # 내용 정제
│   └── cache.py               # 캐싱 시스템
├── tools/                  # MCP 도구
│   ├── dart_api_tools.py      # 기본 DART API
│   └── dart_deep_search_tools.py  # 심층 검색 도구
└── main.py                 # MCP 서버 엔트리포인트
```

## 개발

### 테스트 실행

```bash
# 전체 파이프라인 테스트
python test_pipeline_full.py

# 유닛 테스트
pytest tests/
```

### 코드 포맷팅

```bash
black .
ruff check .
```

## 주요 기술 스택

### 필수 의존성
- `mcp`: Model Context Protocol 라이브러리
- `OpenDartReader`: DART API Python 클라이언트
- `httpx`: 비동기 HTTP 클라이언트
- `beautifulsoup4`: HTML 파싱
- `python-dotenv`: 환경변수 관리

### AI/ML 관련
- `openai`: LLM 클라이언트 (답변 생성용)
- `langextract`: 자연어 쿼리 파싱
- `thefuzz`: 퍼지 문자열 매칭 (기업명 검증)

### 유틸리티
- `diskcache`: 로컬 캐싱
- `aiofiles`: 비동기 파일 I/O
- `pandas`: 데이터 처리 (선택적)

## 라이선스

MIT

## 기여

이슈 및 PR은 언제나 환영합니다!

## 문의

DART API 관련 문의: [DART OpenAPI](https://opendart.fss.or.kr/)