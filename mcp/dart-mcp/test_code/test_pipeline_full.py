#!/usr/bin/env python
"""전체 파이프라인 테스트 - 문서 내용 가져오기 포함"""
import sys
import os
# 상위 디렉토리를 path에 추가 (test_code의 상위인 dart-mcp 디렉토리)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow.dart_orchestrator import DartOrchestrator
from tools import dart_api_tools
import asyncio
import json
from datetime import datetime
from pathlib import Path
import csv

async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    import time
    
    # 로그 디렉토리 생성
    log_dir = Path("test_logs")
    log_dir.mkdir(exist_ok=True)
    
    # 타임스탬프로 로그 파일 이름 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_test_{timestamp}.json"
    
    # 테스트 쿼리들
    test_queries = [
        # "최근 1년 주식매수선택권 부여 공시에 대해 상세 내용을 정리해줘",
        "최근 1개월 상장회사의 인수 합병 공시에서 합병 비율은 어땠는지 찾아봐줘.",
        # "크라우드웍스 타법인 증권양수 공시 찾아서 요약해줘",
        # "2024년 3분기 실적 발표 기업들"
    ]
    
    dart = DartOrchestrator(dart_api_tools)
    
    # 캐시 상태 확인 및 선택적 클리어
    print("💾 캐시 설정:")
    print(f"   Cache Type: {type(dart.document_fetcher.cache).__name__}")
    
    # 캐시를 클리어하고 싶으면 주석 해제
    await dart.document_fetcher.cache.clear()
    print("   🧹 캐시 클리어됨")
    
    # 전체 테스트 결과 저장용
    test_results = {
        "test_time": timestamp,
        "queries": []
    }
    
    for query in test_queries[:1]:  # 첫 번째 쿼리만 테스트
        print("=" * 60)
        print(f"쿼리: {query}")
        print("=" * 60)
        
        # 현재 쿼리 결과 저장용
        query_result = {
            "query": query,
            "start_time": datetime.now().isoformat(),
            "steps": {},
            "timing": {},
            "error": None
        }
        
        try:
            # 시간 측정 변수
            total_start = time.time()
            step_times = {}
            
            # 1. Query Expansion
            step_start = time.time()
            print("\n⏱️ [1/5] Query Expansion 시작...")
            expanded_query = await dart.query_expander.expand_query(query)
            step_times["query_expansion"] = time.time() - step_start
            print(f"   ✓ 완료 ({step_times['query_expansion']:.2f}초)")
            print(f"   → {dart.query_expander.format_result(expanded_query)[:200]}...")
            
            # Query Expansion 결과 저장
            query_result["steps"]["query_expansion"] = {
                "duration": step_times["query_expansion"],
                "result": expanded_query
            }
            
            # 2. Search Execution (제한 없이 모든 결과 가져오기)
            step_start = time.time()
            print("\n⏱️ [2/5] Search Execution 시작...")
            search_results = await dart._execute_searches(expanded_query, 999)  # 실질적으로 제한 없음
            step_times["search"] = time.time() - step_start
            print(f"   ✓ 완료 ({step_times['search']:.2f}초)")
            print(f"   → {len(search_results)}건 검색됨")
            
            # Search 결과 저장 (메타데이터만)
            query_result["steps"]["search"] = {
                "duration": step_times["search"],
                "total_results": len(search_results),
                "results": [
                    {
                        "rcept_no": r.get("rcept_no") or r.get("rcp_no"),
                        "corp_name": r.get("corp_name"),
                        "report_nm": r.get("report_nm"),
                        "rcept_dt": r.get("rcept_dt")
                    }
                    for r in search_results
                ]
            }
            
            # 3. Document Filtering
            step_start = time.time()
            print("\n⏱️ [3/5] Document Filtering 시작...")
            filtered_results = await dart.document_filter.filter_documents(query, search_results, expanded_query)
            step_times["document_filtering"] = time.time() - step_start
            print(f"   ✓ 완료 ({step_times['document_filtering']:.2f}초)")
            print(f"   → {len(search_results)}건 중 {len(filtered_results)}건 필터링됨")
            
            # Document Filtering 결과 저장
            query_result["steps"]["document_filtering"] = {
                "duration": step_times["document_filtering"],
                "total_input": len(search_results),
                "total_filtered": len(filtered_results),
                "filtering_ratio": len(filtered_results) / len(search_results) if search_results else 0,
                "filtered_documents": [
                    {
                        "rcept_no": d.get("rcept_no"),
                        "corp_name": d.get("corp_name"),
                        "report_nm": d.get("report_nm"),
                        "rcept_dt": d.get("rcept_dt"),
                        "relevance_score": d.get("relevance_score", 0)
                    }
                    for d in filtered_results
                ]
            }
            
            # 4. Document Processing (필터링된 문서만 처리)
            step_start = time.time()
            print("\n⏱️ [4/5] Document Processing 시작...")
            processed_docs = await dart._process_documents(filtered_results, expanded_query)
            step_times["document_processing"] = time.time() - step_start
            print(f"   ✓ 완료 ({step_times['document_processing']:.2f}초)")
            print(f"   → {len(processed_docs)}개 문서 처리 완료")
            
            content_count = 0
            if processed_docs:
                content_count = sum(1 for d in processed_docs if d.get('content'))
                print(f"   → 내용 포함 문서: {content_count}개")
            
            # Document Processing 결과 저장
            query_result["steps"]["document_processing"] = {
                "duration": step_times["document_processing"],
                "total_processed": len(processed_docs),
                "content_fetched": content_count,
                "documents": [
                    {
                        "rcept_no": d.get("rcept_no"),
                        "corp_name": d.get("corp_name"),
                        "report_nm": d.get("report_nm"),
                        "has_content": bool(d.get("content")),
                        "content_length": len(d.get("content", "")) if d.get("content") else 0,
                        "source": d.get("source"),
                        "relevance_score": d.get("relevance_score", 0)
                    }
                    for d in processed_docs
                ]
            }
            
            # 5. Synthesis
            step_start = time.time()
            print("\n⏱️ [5/5] Synthesis 시작...")
            synthesis_result = await dart.synthesizer.synthesize(
                query, processed_docs, expanded_query,
                {
                    "total_searched": len(search_results),
                    "total_filtered": len(filtered_results),
                    "total_processed": len(processed_docs)
                }
            )
            step_times["synthesis"] = time.time() - step_start
            print(f"   ✓ 완료 ({step_times['synthesis']:.2f}초)")
            
            # Synthesis 결과 저장
            query_result["steps"]["synthesis"] = {
                "duration": step_times["synthesis"],
                "result": synthesis_result
            }
            
            # 전체 시간
            total_time = time.time() - total_start
            
            # 타이밍 정보 저장
            query_result["timing"] = step_times
            query_result["total_time"] = total_time
            query_result["end_time"] = datetime.now().isoformat()
            
            # 시간 요약
            print("\n" + "=" * 50)
            print("⏰ 소요시간 요약")
            print("=" * 50)
            for step_name, step_time in step_times.items():
                percent = (step_time / total_time) * 100
                bar = "█" * int(percent / 2)
                print(f"{step_name:20s}: {step_time:5.2f}초 ({percent:5.1f}%) {bar}")
            print("-" * 50)
            print(f"{'전체':20s}: {total_time:5.2f}초")
            
            # 결과 JSON으로 변환
            result_json = json.dumps(synthesis_result, ensure_ascii=False, indent=2)
            
            # 결과 파싱
            result = json.loads(result_json)
            
            # 결과 요약 출력
            if result.get("status") == "error":
                print(f"❌ 에러: {result.get('error')}")
            else:
                print("\n📊 검색 결과 요약:")
                if "summary" in result:
                    summary = result["summary"]
                    print(f"  - 총 문서 수: {summary.get('total_documents', 0)}")
                    print(f"  - 기간: {summary.get('date_range', {})}")
                    print(f"  - 기업: {', '.join(summary.get('companies', []))}")
                
                # 필터링 통계 추가
                print(f"\n📈 처리 통계:")
                print(f"  - 검색된 문서: {len(search_results)}건")
                print(f"  - 필터링된 문서: {len(filtered_results)}건")
                print(f"  - 처리된 문서: {len(processed_docs)}건")
                print(f"  - 내용 가져온 문서: {content_count}건")
                
                print("\n📝 LLM 답변:")
                if "answer" in result:
                    answer = result["answer"]
                    # 긴 답변은 줄여서 표시
                    if len(answer) > 500:
                        print(f"  {answer[:500]}...")
                    else:
                        print(f"  {answer}")
                
                print("\n📄 상위 문서들:")
                if "documents" in result:
                    for i, doc in enumerate(result["documents"][:3], 1):
                        print(f"\n  [{i}] {doc.get('company', 'N/A')} - {doc.get('title', 'N/A')}")
                        print(f"      날짜: {doc.get('date', 'N/A')}")
                        print(f"      접수번호: {doc.get('rcept_no', 'N/A')}")
                        
                        # 문서 내용 소스 확인
                        if doc.get("source"):
                            print(f"      소스: {doc['source']}")
                        
                        # 내용 미리보기
                        if doc.get("content"):
                            content_preview = doc["content"][:200] if doc["content"] else "내용 없음"
                            print(f"      내용 미리보기: {content_preview}...")
                        elif doc.get("structured_data"):
                            print(f"      구조화된 데이터 포함")
                        else:
                            print(f"      내용 가져오기 실패")
                
                print("\n🔑 핵심 정보:")
                if "key_findings" in result:
                    for finding in result["key_findings"][:3]:
                        print(f"  • {finding}")
            
        except Exception as e:
            print(f"❌ 파이프라인 실행 중 오류: {e}")
            import traceback
            traceback.print_exc()
            
            # 에러 정보 저장
            query_result["error"] = {
                "message": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        
        # 쿼리 결과를 전체 결과에 추가
        test_results["queries"].append(query_result)
        
        # 각 쿼리마다 중간 저장
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 결과 저장됨: {log_file}")
        
        print("\n" + "=" * 60)
    
    # 최종 요약 정보 추가
    test_results["summary"] = {
        "total_queries": len(test_results["queries"]),
        "successful": sum(1 for q in test_results["queries"] if not q.get("error")),
        "failed": sum(1 for q in test_results["queries"] if q.get("error")),
        "total_documents_processed": sum(
            q.get("steps", {}).get("document_processing", {}).get("total_processed", 0)
            for q in test_results["queries"]
        ),
        "total_documents_with_content": sum(
            q.get("steps", {}).get("document_processing", {}).get("content_fetched", 0)
            for q in test_results["queries"]
        )
    }
    
    # 최종 저장
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    
    # CSV 파일로도 저장 (간단한 요약)
    csv_file = log_dir / f"pipeline_summary_{timestamp}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Query', 'Total Time', 'Search Results', 'Filtered Results', 
                        'Documents Processed', 'Documents with Content', 'Status'])
        
        for q in test_results["queries"]:
            writer.writerow([
                q["query"][:50],  # 쿼리 (최대 50자)
                f"{q.get('total_time', 0):.2f}",
                q.get("steps", {}).get("search", {}).get("total_results", 0),
                q.get("steps", {}).get("document_filtering", {}).get("total_filtered", 0),
                q.get("steps", {}).get("document_processing", {}).get("total_processed", 0),
                q.get("steps", {}).get("document_processing", {}).get("content_fetched", 0),
                "ERROR" if q.get("error") else "SUCCESS"
            ])
    
    print(f"\n✅ 모든 테스트 결과가 저장되었습니다:")
    print(f"   - JSON: {log_file}")
    print(f"   - CSV: {csv_file}")

async def test_document_fetcher():
    """문서 가져오기 모듈 단독 테스트"""
    from workflow.utils.document_fetcher import DocumentFetcherV2
    
    print("\n" + "=" * 60)
    print("문서 가져오기 모듈 테스트")
    print("=" * 60)
    
    fetcher = DocumentFetcherV2(dart_api_tools)
    
    # 테스트용 문서 정보
    test_doc = {
        "rcept_no": "20240101000001",  # 예시 접수번호
        "corp_code": "00126380",  # 삼성전자 코드
        "corp_name": "삼성전자",
        "report_nm": "주요사항보고서(자기주식취득결정)",
        "report_type": "B001"
    }
    
    print(f"테스트 문서: {test_doc['corp_name']} - {test_doc['report_nm']}")
    
    # 문서 내용 가져오기
    result = await fetcher.fetch_document_content(
        rcept_no=test_doc["rcept_no"],
        corp_code=test_doc["corp_code"],
        report_type=test_doc["report_type"],
        fetch_mode="auto"
    )
    
    if result.get("error"):
        print(f"❌ 에러: {result['error']}")
    else:
        print(f"✅ 소스: {result.get('source', 'unknown')}")
        
        if result.get("structured_data"):
            print("✅ 구조화된 데이터 획득")
            for key in result["structured_data"].keys():
                print(f"  - {key}")
        
        if result.get("content"):
            print(f"✅ 내용 길이: {len(result['content'])} 글자")
            print(f"내용 미리보기:\n{result['content'][:300]}...")

async def main():
    """메인 테스트"""
    print("🚀 DART 파이프라인 전체 테스트 시작\n")
    
    # 문서 가져오기 모듈 테스트
    # await test_document_fetcher()
    
    # 전체 파이프라인 테스트
    await test_full_pipeline()
    
    print("\n✅ 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())