# DART Orchestrator 워크플로우 분석

## 전체 파이프라인 흐름 (개선된 버전)

```
사용자 쿼리 → search_pipeline() 
  ↓
Phase 1: Query Expansion (쿼리 확장)
  ↓
Phase 2: Search Execution (검색 실행) 
  ↓
Phase 3: Document Filtering (문서 필터링) ← ✅ 여기서 필터링 발생
  ↓
Phase 4: Document Processing (문서 처리)
  ↓
Phase 5: Synthesis (최종 답변 생성)
```

## 세부 단계별 분석

### Phase 1: Query Expansion (`query_expander.expand_query()`)
- **역할**: 사용자 쿼리를 구조화된 검색 파라미터로 확장
- **출력**: 
  - companies (기업명 리스트)
  - corp_codes (기업 코드)
  - date_range (날짜 범위)
  - doc_types (문서 유형)
  - keywords (키워드)

### Phase 2: Search Execution (`_execute_searches()`)
- **역할**: DART API를 통한 공시 검색
- **동작**:
  1. 검색 파라미터 생성 (`query_expander.create_search_params()`)
  2. 병렬/순차 검색 실행
  3. 결과 중복 제거 (`_deduplicate_results()`)
  4. 최대 `max_results_per_search` (기본 30개) 제한
- **⚠️ 잠재 이슈**: 검색 결과가 많을 때 30개로 제한 (greedy하지 않음)

### Phase 3: Document Filtering (`document_filter.filter_documents()`)
- **역할**: 검색된 문서 중 관련성 높은 문서만 선별
- **동작**:
  1. ~~관련성 점수 계산~~ (제거됨)
  2. LLM 기반 또는 규칙 기반 필터링
  3. 최대 30개의 관련 문서만 선택 (규칙 기반)
- **✅ 개선점**: 
  - 불필요한 문서 처리 방지, API 호출 최적화
  - 필터링 로직을 별도 모듈로 분리 (`utils/document_filter.py`)

### Phase 4: Document Processing (`_process_documents()`)
- **역할**: 필터링된 문서의 상세 내용 가져오기
- **동작**:
  1. 필터링된 문서의 기본 정보 구성
  2. `document_fetcher.fetch_multiple_documents()` 호출
  3. 가져온 내용을 문서 정보에 병합
- **✅ 개선점**: 필터링된 문서만 처리하여 효율성 증대

### Phase 5: Synthesis (`synthesizer.synthesize()`)
- **역할**: 최종 답변 생성
- **입력**: 처리된 문서들과 필터링 통계 정보
- **동작**:
  1. 문서 분석 (`_analyze_documents`)
  2. 핵심 정보 추출 (`_extract_key_findings`)
  3. 시계열 분석 (`_create_timeline`)
  4. LLM 기반 자연어 답변 생성 (`_generate_llm_answer`)
  5. 최종 응답 구성

## ✅ 해결된 문제점들

### 1. **중복 필터링 문제 해결**
```
기존: Phase 2 → Phase 3 (모든 문서 처리) → Phase 4 (늦은 필터링)
개선: Phase 2 → Phase 3 (필터링) → Phase 4 (필터링된 문서만 처리)
```

### 2. **Greedy 동작 제거**
- **Phase 3**: 이제 필터링이 먼저 발생
- **Phase 4**: 필터링된 문서만 처리하여 효율성 증대
- **불필요한 API 호출 제거**

### 3. **모듈 책임 명확화**
- **orchestrator**: 파이프라인 조정만 (필터링 로직 분리됨)
- **document_filter**: 문서 필터링 전담 (새로 분리됨)
- **document_fetcher**: 순수하게 문서 내용 가져오기만
- **synthesizer**: 최종 답변 생성 (관련성 점수 로직 제거됨)
- **sufficiency_checker**: 관련성 점수 로직 제거됨

## 🎯 구현된 개선사항

### 1. **새로운 필터링 시점 (개선됨)**
```python
# Phase 3: Document Filtering (utils/document_filter.py로 분리)
class DocumentFilter:
    async def filter_documents():
        # 1. ~~관련성 점수 계산~~ (제거됨 - 무의미했음)
        
        # 2. LLM 또는 규칙 기반 필터링
        if self.llm_client:
            return await self._llm_based_filtering(query, search_results, expanded_query)
        else:
            return self._rule_based_filtering(query, search_results, expanded_query)
        
        # 3. 프롬프트 템플릿 활용 (workflow/prompts/document_filter.txt)
```

### 2. **최적화된 파라미터 (업데이트됨)**
```python
# 실제 적용된 파라미터
MAX_DOCS_TO_FILTER = 100   # 필터링 대상 최대 문서 수 (증가)
MAX_DOCS_TO_RETURN = 30    # 필터링 후 최대 반환 문서 수 (증가)
BATCH_SIZE = 100           # LLM 필터링 배치 크기 (증가)
~~RELEVANCE_THRESHOLD~~    # 제거됨 (관련성 점수 로직 삭제)
```

### 3. **LLM 기반 스마트 필터링 (개선됨)**
- 배치 처리로 성능 최적화 (배치 크기 100으로 증가)
- JSON 형식 응답으로 구조화된 결과
- 실패시 규칙 기반 필터링으로 폴백
- **새로운 기능**: 프롬프트 템플릿 파일 활용 (`workflow/prompts/document_filter.txt`)
- **코드 분리**: 필터링 로직이 `utils/document_filter.py`로 독립

## 📊 성능 개선 결과

### 기존 방식
- 30개 문서 검색 → 30개 모두 내용 가져오기 → 필터링 → 10개만 사용
- **낭비**: 20개 문서의 불필요한 API 호출

### 개선된 방식 (현재)
- 30개 문서 검색 → 필터링 → 30개만 내용 가져오기 → 처리 완료
- **절약**: 불필요한 관련성 점수 계산 제거로 성능 향상
- **개선**: 모듈화로 유지보수성 증대

## 결론

**성공적으로 해결된 문제들**:
1. ✅ 중복 필터링 제거
2. ✅ Greedy 모듈 동작 최적화
3. ✅ 불필요한 API 호출 방지
4. ✅ 모듈 책임 명확화
5. ✅ **새로 추가**: 무의미한 관련성 점수 로직 제거
6. ✅ **새로 추가**: 필터링 로직 모듈 분리 (`utils/document_filter.py`)

**새로운 워크플로우의 장점**:
- 🚀 성능 개선 (불필요한 계산 제거)
- 🎯 정확한 필터링 (LLM 기반 + 프롬프트 템플릿)
- 🔧 유지보수성 향상 (모듈 분리된 구조)
- ⚡ 응답 시간 단축 (관련성 점수 계산 제거)
- 📝 **새로 추가**: 템플릿 기반 프롬프트 관리

## 🆕 최근 개선사항 (2024.09.19)

### 1. **관련성 점수 로직 완전 제거**
```python
# 제거된 기능들
- _calculate_relevance() 메서드
- relevance_score 변수들
- 관련성 기반 정렬 로직
- sufficiency_checker의 relevance_score 계산
- synthesizer의 relevance 관련 처리
```

**이유**: 실제로는 무의미한 점수 계산이었으며, LLM 필터링이 더 정확함

### 2. **필터링 로직 모듈 분리**
```
workflow/dart_orchestrator.py
  ↓ 130줄 제거
utils/document_filter.py (새로 생성)
  ↓ 기능 분리
- DocumentFilter 클래스
- _llm_based_filtering() 메서드  
- _rule_based_filtering() 메서드
- 프롬프트 템플릿 로딩 기능
```

### 3. **프롬프트 템플릿 통합**
- `workflow/prompts/document_filter.txt` 활용
- `sufficiency_checker.py`와 `document_filter.py`에서 공통 사용
- 중앙화된 프롬프트 관리로 일관성 향상

### 4. **파라미터 최적화**
```python
# 변경된 파라미터들
MAX_DOCS_TO_FILTER: 30 → 100    # 더 많은 문서 검토
MAX_DOCS_TO_RETURN: 15 → 30     # 더 많은 문서 반환
BATCH_SIZE: 10 → 100            # 배치 크기 증가
```

### 5. **코드 구조 개선**
- `dart_orchestrator.py`: 130줄 감소 (필터링 로직 분리)
- 모듈별 책임 명확화
- 재사용 가능한 독립적인 필터링 모듈

## 🔍 Phase별 세부 분석

### Phase 4: Document Processing 상세 흐름
```python
async def _process_documents():
    # 1. 필터링된 문서의 기본 정보 구성
    for doc in filtered_results:
        doc_info = {
            "rcept_no": doc.get("rcept_no"),
            "corp_name": doc.get("corp_name"),
            "report_nm": doc.get("report_nm"),
            # ... 메타데이터
        }
    
    # 2. 문서 내용 가져오기 (DocumentFetcher 사용)
    fetched_contents = await document_fetcher.fetch_multiple_documents(
        docs_to_fetch,
        max_concurrent=3,
        detailed_types=detailed_types
    )
    
    # 3. 가져온 내용을 문서 정보에 병합
    for doc, fetched in zip(processed, fetched_contents):
        doc.update(fetched)  # content, structured_data, source 등
```

### Phase 5: Synthesis 상세 분석

#### 1. 문서 분석 단계 (업데이트됨)
```python
analysis = {
    "total_count": len(documents),
    "companies": set(),           # 관련 기업들
    "date_range": {},            # 날짜 범위
    "report_types": {},          # 보고서 유형별 집계
    "keywords_found": set(),     # 매칭된 키워드들
    # ~~"avg_relevance": 0.0~~   # 제거됨 (관련성 점수 로직 삭제)
}
```

#### 2. 핵심 정보 추출 (업데이트됨)
- **상위 5개 문서**에서 핵심 정보 추출
- 각 문서별로 기업명, 날짜, 제목, 요약, ~~관련성~~, URL 포함
- **변경**: 관련성 점수 필드 제거됨

#### 3. 시계열 분석
- 날짜별로 문서 그룹화
- **최근 10일간** 타임라인 생성
- 각 날짜당 **최대 3개 이벤트**만 포함

#### 4. LLM 답변 생성 과정

**현재 프롬프트 구조**:
```
사용자 질의: {query}
검색 결과 분석: (통계 정보)
주요 발견사항: {key_findings}
최근 타임라인: {timeline}

### 문서 1-5 (실제 내용 포함)
- 기업/제목/날짜/접수번호
- 내용: 실제 문서 텍스트 (최대 1500자)
- 구조화 데이터: 추출된 정보
```

#### 5. 최종 응답 구조
```json
{
    "query": "사용자 질의",
    "answer": "LLM 생성 답변",
    "summary": {
        "total_documents": 개수,
        "date_range": 기간,
        "companies": 기업목록,
        "confidence": 신뢰도
    },
    "documents": [모든 문서 정보],  // ← 여기서 상위문서들 출력
    "metadata": {...}
}
```

## ⚠️ 현재 문제점들

### 1. **Document Processing 문제**
- **문제**: 실제 API 문서 내용 가져오기가 불완전
- **원인**: DocumentFetcher가 DART API에서 원본 문서를 제대로 가져오지 못함
- **해결 필요**: API를 통한 실제 공시 원문 가져오기 최적화

### 2. **Synthesis 출력 문제**
- **문제**: 사용자 쿼리와 무관한 정보도 함께 출력됨
  - `"documents"` 배열에 모든 문서 반환
  - `"key_findings"` 상위 문서들 자동 포함
- **원인**: 
  ```python
  # synthesizer.py:79
  "documents": self._format_documents(documents),  # 모든 문서 반환
  ```

### 3. **프롬프트 최적화 필요**
- **현재**: 단순한 통계 정보와 메타데이터 위주
- **개선 필요**: 실제 문서 내용 기반 정확한 답변 생성
- **문제**: `synthesis.txt` 프롬프트가 너무 간단함

## 🎯 개선 방안

### 1. **Document Processing 개선**
- DocumentFetcher에서 DART 원문 API 활용도 높이기
- 구조화된 데이터 추출 로직 강화

### 2. **Synthesis 출력 최적화**
```python
# 사용자 쿼리에 맞는 선별적 출력
response = {
    "query": query,
    "answer": narrative,  # 핵심 답변만
    # documents는 answer에 포함된 것만 선별적으로
}
```

### 3. **프롬프트 개선**
- 실제 문서 내용 기반 답변 생성
- 쿼리별 맞춤형 답변 구조
- 불필요한 메타데이터 출력 최소화