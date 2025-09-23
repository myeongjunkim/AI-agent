# DART MCP (Model Context Protocol) Server - PRD

## 1. 프로젝트 개요

### 1.1 목적
한국 전자공시시스템(DART)의 기업 공시 데이터를 효율적으로 검색, 분석, 처리할 수 있는 MCP 서버 구현

### 1.2 주요 기능
- DART API를 통한 기업 공시 검색 및 분석
- LLM 기반 지능형 쿼리 확장 및 문서 분류
- 구조화된 데이터 추출 및 종합 답변 생성
- 효율적인 캐싱 및 성능 최적화

## 시스템 아키텍처

### 파이프라인 구조

#### 1. Planning Phase (Supervisor Agent) ✅

- [x] 사용자 쿼리 분석
- [x] DART 문서 상세유형 자동 선택 (LLM 기반)
- [x] 검색 전략 수립
- [x] 필요한 agent/도구 결정


#### 2. Query Expansion Phase ✅

- [x] 쿼리 키워드 추출 및 확장
- [x] 날짜 범위 파싱 (예: "최근 1년" → YYYYMMDD 형식)
- [x] 기업명을 corp_code로 변환


#### 3. Search Phase ✅

- [x] DART 공시검색 API 호출
- [x] 최대 100건 검색 (환경변수로 설정 가능)
- [x] 페이징 처리


#### 4. Document Processing Phase ✅

- [x] 검색 결과에서 문서 고유번호(rcept_no) 추출
- [x] 상세 보고서 API 존재 여부 확인
- [x] API 있으면: 주요사항보고서 API 호출
- [x] API 없으면: 원본 파일 다운로드 (ZIP/XML)


#### 5. Parsing & Extraction Phase ✅

- [x] API 응답 또는 다운로드 파일 파싱
- [x] 핵심 정보 추출
- [x] 구조화된 데이터로 변환


#### 6. Sufficiency Check Phase ✅

- [x] 수집된 정보가 질의 답변에 충분한지 검토
- [x] 부족시 추가 검색/다운로드 수행


#### 7. Final Synthesis (Supervisor Agent) ✅

- [x] 모든 결과 취합
- [x] 사용자 질의에 맞는 최종 답변 생성



## 문서 상세유형 매핑 테이블

### A: 정기보고서

A001: 사업보고서 (연간보고서, 연차보고서)
A002: 반기보고서
A003: 분기보고서 (1분기, 3분기)
A004: 등록법인결산서류
A005: 소액공모법인결산서류

### B: 주요사항보고서 (핵심)

B001: 주요사항보고서

자기주식 관련: 자기주식, 자사주, 취득, 처분, 신탁
주식매수선택권: 매수선택권, 스톡옵션, 취소결의
임원/이사회: 대표이사, 임원, 선임, 해임, 사임
주요주주: 대주주, 최대주주, 지분변동
구조변경: 합병, 분할, 영업양도, 주식교환
자본변동: 유상증자, 무상증자, 감자
기타: 회생절차, 파산, 소송


B002: 주요경영사항신고
B003: 최대주주등과의거래신고

### C: 증권신고서

C001: 증권신고(지분증권) - IPO, 상장
C002: 증권신고(채무증권) - 사채, 회사채
C003: 증권신고(파생결합증권) - ELS, DLS
C004-C011: 기타 증권신고 및 소액공모

### D: 지분공시

D001: 주식등의대량보유상황보고서 (5%룰)
D002: 임원·주요주주특정증권등소유상황보고서
D003: 의결권대리행사권유
D004: 공개매수
D005: 거래계획보고서

### E: 기타주요공시

E001: 자기주식취득/처분
E002: 신탁계약체결/해지
E003: 합병등종료보고서
E004: 주식매수선택권부여
E005: 사외이사신고
E006: 주주총회소집보고서

### F: 감사보고서

F001: 감사보고서
F002: 연결감사보고서

### G-J: 기타 공시

G: 집합투자 관련
H: 자산유동화 관련
I: 거래소공시 (수시공시, 공정공시)
J: 공정위공시 (대규모내부거래 등)

## 환경변수 설정 (.env)

```bash
# DART API
DART_API_KEY=your_api_key_here

# File Storage
DART_DOWNLOAD_PATH=./downloads/dart
DART_CACHE_PATH=./cache/dart

# Search Configuration  
DART_MAX_SEARCH_RESULTS=100
DART_API_RATE_LIMIT=1000

# Processing
DART_PARALLEL_DOWNLOADS=5
DART_PARSE_TIMEOUT=30000
```

## API 엔드포인트

### 필수 사용

공시검색 API: https://opendart.fss.or.kr/api/list.json

### 조건부 사용

주요사항보고서 API: https://opendart.fss.or.kr/api/majorReport.json
사업보고서 주요정보 API: https://opendart.fss.or.kr/api/fnlttSinglAcnt.json
공시서류 원본파일: https://opendart.fss.or.kr/api/document.xml
기업명고유번호: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018

## 검색 파라미터 구성

```python
# Python 딕셔너리 형태로 변경
search_params = {
    "crtfc_key": "API_KEY",           # 필수
    "bgn_de": "20240101",             # 시작일 (YYYYMMDD)
    "end_de": "20241231",             # 종료일 (YYYYMMDD)
    "pblntf_detail_ty": "B001,E004",  # 문서유형 (복수 가능)
    "corp_code": "00126380",          # 기업코드 (선택)
    "page_no": 1,                     # 페이지 번호
    "page_count": 100,                # 페이지당 건수 (최대 100)
    "sort": "date",                   # 정렬: date, crp, rpt
    "sort_mth": "desc"                # 정렬방법: asc, desc
}
```

## 구현 우선순위

### Phase 1 (MVP)

사용자 쿼리 → 문서유형 자동 선택 로직
DART 공시검색 API 연동
검색 결과 파싱 및 정리
기본적인 답변 생성

### Phase 2

원본 파일 다운로드 및 캐싱
주요사항보고서 상세 API 연동
복잡한 쿼리 처리 (복수 기업, 비교 분석)

### Phase 3

PDF/XML 파싱 기능
고급 분석 기능 (트렌드, 패턴)
성능 최적화

## 주요 구현 지침

### 문서유형 선택 로직

사용자 쿼리에서 키워드를 추출하여 적절한 pblntf_detail_ty 코드 선택
복수 문서유형 선택 가능 (최대 3개 권장)
신뢰도 기반 우선순위 정렬


### API 제한사항 대응

공시 제목 검색 불가 → 문서유형 필터링으로 대체
일일 호출 제한 → 캐싱 및 Rate limiting 구현
검색 결과 100건 제한 → 날짜 범위 분할 검색


### 에러 처리

API 호출 실패시 3회 재시도
타임아웃 설정 (30초)
상세한 에러 로깅


## 파일 구조

```
@dart-mcp/
├── main.py                           # MCP 서버 엔트리포인트
├── pyproject.toml                    # 프로젝트 설정 및 의존성
├── .env                              # 환경변수 설정
├── workflow/                         # 오케스트레이션 및 파이프라인
│   ├── __init__.py
│   ├── dart_orchestrator.py         # DART 심층검색 메인 파이프라인
│   ├── utils/                       # 워크플로우 유틸리티
│   │   ├── __init__.py
│   │   ├── query_planner.py        # 쿼리 계획 및 분해
│   │   ├── query_expander.py       # 쿼리 확장 (날짜, 기업명 처리)
│   │   ├── doc_type_mapper.py      # 문서유형 자동 매핑
│   │   ├── sufficiency_checker.py  # 정보 충분성 검사
│   │   └── synthesizer.py          # 최종 답변 생성
├── tools/                            # MCP 도구 정의 (기존 구현 활용)
│   ├── __init__.py
│   ├── dart_api_tools.py           # DART API 기본 도구 (이미 구현됨)
│   └── dart_deep_search_tools.py   # 심층 검색 도구 (신규)
├── utils/                            # 유틸리티
│   ├── __init__.py
│   ├── logging.py                  # MCP 로깅 시스템
│   ├── parse_dart.py               # DART 문서 파싱
│   ├── cache.py                    # 캐싱 시스템
│   ├── config_loader.py            # 설정 로더
│   ├── corp_code_mapper.py         # 기업명↔기업코드 변환
│   ├── date_parser.py              # 날짜 표현 파싱
│   └── document_extractor.py       # PDF/XML 정보 추출
├── prompts/                          # LLM 프롬프트 템플릿
│   ├── query_planner.txt           # 쿼리 계획 프롬프트
│   ├── doc_type_selector.txt       # 문서유형 선택 프롬프트
│   ├── synthesizer.txt             # 답변 생성 프롬프트
│   └── sufficiency_checker.txt     # 충분성 검사 프롬프트
├── tests/                            # 테스트
│   ├── __init__.py
│   ├── test_dart_api.py
│   ├── test_orchestrator.py
│   ├── test_parser.py
│   └── fixtures/                   # 테스트 데이터
│       └── sample_responses.json
├── cache/                            # 캐시 디렉토리
│   └── dart/
└── downloads/                        # 다운로드 디렉토리
    └── dart/
```

## 테스트 케이스

"최근 1년간 매수선택권 취소결의 사례는?"

예상 문서유형: B001, E004
날짜 범위: 최근 1년


"최근 1년간 상장회사 합병 비율은?"

예상 문서유형: E001, B001, E002
기업코드 변환 필요


## 상세 개발 계획

### Phase 1: 기반 구조 구축 (1주차)

#### 1.1 프로젝트 초기화
- [x] 기본 디렉토리 구조 생성
- [x] pyproject.toml 설정
- [x] main.py 기본 구조
- [x] 환경변수 설정 (.env)

#### 1.2 핵심 유틸리티 구현
- [x] **utils/logging.py** - MCP 로깅 시스템 구현
- [x] **utils/config_loader.py** - 설정 및 API 키 관리
- [x] **utils/corp_code_mapper.py** - 기업명↔코드 변환
- [x] **utils/date_parser.py** - "최근 1년" → YYYYMMDD 변환

#### 1.3 기존 도구 확인 및 보완
- [x] **tools/dart_api_tools.py** - 기존 구현 확인 (OpenDartReader 활용)
- [x] **tools/dart_deep_search_tools.py** - 심층 검색 도구 추가

### Phase 2: 워크플로우 구현 (2주차)

#### 2.1 쿼리 처리 유틸리티
- [x] **workflow/utils/query_planner.py** - 쿼리 분해
- [x] **workflow/utils/doc_type_mapper.py** - 문서유형 자동 선택
- [x] **workflow/utils/query_expander.py** - 쿼리 확장

#### 2.2 메인 오케스트레이터
- [x] **workflow/dart_orchestrator.py** - 파이프라인 구현
  - [x] Planning Phase 구현
  - [x] Search Phase 구현 (병렬 처리)
  - [x] Document Processing Phase
  - [x] Sufficiency Check Phase
  - [x] Synthesis Phase

#### 2.3 MCP 도구 통합
- [x] **tools/dart_deep_search_tools.py** - 심층 검색 도구 등록
- [x] 기존 dart_api_tools.py와 통합
- [x] MCP 서버 테스트

### Phase 3: 고급 기능 (3주차)

#### 3.1 문서 처리 강화
- [x] **utils/document_extractor.py** - PDF/XML 파싱 강화 (document_downloader.py로 구현)
- [x] 기존 parse_dart.py 확장

#### 3.2 캐싱 시스템
- [x] **utils/cache.py** - 캐싱 구현
- [x] API 호출 최적화
- [x] Rate limiting 구현

#### 3.3 답변 품질 향상
- [x] **workflow/utils/synthesizer.py** - 답변 생성 개선
- [x] **workflow/utils/sufficiency_checker.py** - 충분성 검사 개선

### Phase 4: 테스트 및 최적화 (4주차)

#### 4.1 테스트 구현
- [x] 단위 테스트 작성 (test_simple.py, test_pipeline_full.py)
- [x] 통합 테스트 작성
- [x] 실제 시나리오 테스트

#### 4.2 성능 최적화
- [x] 기본 병렬 처리 구현 (3개 동시 처리)
- [ ] 고급 병렬 처리 최적화 (동적 조절)
- [ ] 메모리 사용 최적화 (스트리밍 처리)
- [x] API 호출 최소화 (캐싱 구현)
- [x] Rate Limiting 구현

#### 4.3 문서화
- [x] README.md 업데이트
- [ ] API 문서 작성
- [ ] 사용 예제 작성

## 구현 우선순위 (수정)

### 즉시 구현 (MVP)
1. **dart_orchestrator.py** - 메인 파이프라인
2. **doc_type_mapper.py** - 문서유형 자동 선택
3. **query_expander.py** - 날짜/기업명 처리
4. **dart_deep_search_tools.py** - 심층 검색 MCP 도구

### 2차 구현
1. **cache.py** - 캐싱 시스템
2. **sufficiency_checker.py** - 충분성 검사
3. **synthesizer.py** - 답변 생성

### 3차 구현
1. **document_extractor.py** - PDF/XML 파싱
2. **synthesizer.py** - 고급 답변 생성
3. 성능 최적화

## 기술 스택

### 필수 의존성
- **mcp** ≥ 1.0.0 - MCP 서버 프레임워크
- **OpenDartReader** ≥ 0.2.4 - DART API 클라이언트
- **httpx** ≥ 0.27.0 - 비동기 HTTP 클라이언트
- **beautifulsoup4** ≥ 4.12.0 - HTML 파싱
- **python-dotenv** ≥ 1.0.0 - 환경변수 관리

### 선택적 의존성
- **openai** - LLM 클라이언트 (vLLM 서버용)
- **pandas** - 데이터 처리
- **pdfplumber** - PDF 파싱
- **lxml** - XML 파싱

### 개발 도구
- **pytest** - 테스트 프레임워크
- **pytest-asyncio** - 비동기 테스트
- **black** - 코드 포매터
- **ruff** - 린터

## 아키텍처 설계 원칙

### tools/와 workflow/의 역할 분리

#### tools/ 디렉토리
- **목적**: MCP 도구 등록 및 외부 인터페이스
- **구성**:
  - `dart_api_tools.py`: 기본 DART API 도구 (이미 구현됨)
    - OpenDartReader 활용한 기본 API 호출
    - 개별 공시 조회, 재무제표, 기업정보 등
  - `dart_deep_search_tools.py`: 심층 검색 도구 (신규)
    - workflow 오케스트레이터 호출
    - 복잡한 질의 처리

#### workflow/ 디렉토리
- **목적**: 비즈니스 로직 및 파이프라인
- **구성**:
  - `dart_orchestrator.py`: 메인 파이프라인
    - 기존 dart_api_tools.py의 함수들을 활용
    - 병렬 처리, 충분성 검사, 답변 생성
  - `utils/`: 워크플로우 유틸리티

### 데이터 흐름
```
사용자 질의
    ↓
dart_deep_search_tools.py (MCP 인터페이스)
    ↓
dart_orchestrator.py (파이프라인)
    ↓
dart_api_tools.py (기본 API 호출)
    ↓
OpenDartReader (DART API)
```

## 참고사항

- @deepresearch-mcp/workflow의 파이프라인 구조를 최대한 재사용
- 기존 dart_api_tools.py의 구현을 최대한 활용
- 각 Phase는 독립적인 모듈로 분리
- 응답 시간은 1시간 이내 허용 (성능보다 정확도 우선)
- 비동기 처리로 성능 최적화
- 상세한 로깅으로 디버깅 용이성 확보
