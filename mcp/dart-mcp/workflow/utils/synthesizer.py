"""
답변 생성기 (Synthesizer)
수집된 DART 공시 정보를 종합하여 사용자 질의에 대한 답변 생성
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from utils.logging import get_logger
from utils.content_cleaner import clean_for_llm

logger = get_logger("synthesizer")


class DartSynthesizer:
    """DART 검색 결과 종합 및 답변 생성"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 클라이언트 (선택적)
        """
        self.llm_client = llm_client
        self.synthesis_prompt = self._load_prompt()
        
    async def synthesize(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any],
        sufficiency_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        검색 결과를 종합하여 답변 생성
        
        Args:
            query: 원본 사용자 쿼리
            documents: 검색된 문서들
            expanded_query: 확장된 쿼리 정보
            sufficiency_result: 충분성 검사 결과
            
        Returns:
            종합된 답변 딕셔너리
        """
        logger.info(f"Synthesizing answer for query: {query}")
        
        # 1. 문서 분석
        analysis = await self._analyze_documents(documents, expanded_query)
        
        # 2. 핵심 정보 추출
        key_findings = await self._extract_key_findings(documents, expanded_query)
        
        # 3. 시계열 분석
        timeline = self._create_timeline(documents)
        
        # 4. 자연어 답변 생성
        if self.llm_client:
            narrative = await self._generate_llm_answer(
                query, analysis, key_findings, timeline, documents
            )
        else:
            narrative = self._generate_rule_based_answer(
                query, analysis, key_findings, timeline
            )
        
        # 5. 최종 응답 구성 (간소화)
        response = {
            "query": query,
            "answer": narrative,
            "summary": {
                "total_documents": len(documents),
                "date_range": analysis["date_range"],
                "companies": list(analysis["companies"]),
                "confidence": sufficiency_result.get("confidence", 0.0) if sufficiency_result else 0.0
            },
            "documents": self._format_documents(documents),  # 모든 문서 반환
            "metadata": {
                "synthesized_at": datetime.now().isoformat(),
                "sufficiency": sufficiency_result.get("is_sufficient", False) if sufficiency_result else True
            }
        }
        
        return response
    
    async def _analyze_documents(
        self,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """문서 분석"""
        analysis = {
            "total_count": len(documents),
            "companies": set(),
            "date_range": {"start": None, "end": None},
            "report_types": defaultdict(int),
            "keywords_found": set(),
        }
        
        if not documents:
            return analysis
        
        dates = []
        
        for doc in documents:
            # 기업명
            if doc.get("corp_name"):
                analysis["companies"].add(doc["corp_name"])
            
            # 날짜
            if doc.get("rcept_dt"):
                dates.append(doc["rcept_dt"])
            
            # 보고서 유형
            if doc.get("report_nm"):
                analysis["report_types"][doc["report_nm"]] += 1
            
        
        # 날짜 범위
        if dates:
            analysis["date_range"]["start"] = min(dates)
            analysis["date_range"]["end"] = max(dates)
        
        
        # 키워드 매칭
        for keyword in expanded_query.get("keywords", []):
            keyword_lower = keyword.lower()
            for doc in documents:
                text = f"{doc.get('report_nm', '')} {doc.get('summary', '')}".lower()
                if keyword_lower in text:
                    analysis["keywords_found"].add(keyword)
                    break
        
        return analysis
    
    async def _extract_key_findings(
        self,
        documents: List[Dict[str, Any]],
        expanded_query: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """핵심 발견사항 추출"""
        findings = []
        
        # 상위 5개 문서에서 핵심 정보 추출
        for doc in documents[:5]:
            finding = {
                "company": doc.get("corp_name", "Unknown"),
                "date": doc.get("rcept_dt", ""),
                "title": doc.get("report_nm", ""),
                "summary": doc.get("summary", ""),
                "url": self._generate_dart_url(doc.get("rcept_no"))
            }
            findings.append(finding)
        
        return findings
    
    def _create_timeline(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """시계열 정보 생성"""
        timeline = []
        
        # 날짜별로 그룹화
        by_date = defaultdict(list)
        for doc in documents:
            if doc.get("rcept_dt"):
                by_date[doc["rcept_dt"]].append(doc)
        
        # 정렬하여 타임라인 생성
        for date in sorted(by_date.keys(), reverse=True)[:10]:  # 최근 10일
            docs = by_date[date]
            timeline.append({
                "date": date,
                "count": len(docs),
                "events": [
                    {
                        "company": d.get("corp_name", ""),
                        "title": d.get("report_nm", ""),
                        "rcept_no": d.get("rcept_no", "")
                    }
                    for d in docs[:3]  # 각 날짜당 최대 3개
                ]
            })
        
        return timeline
    
    def _summarize_by_company(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """기업별 요약"""
        by_company = defaultdict(lambda: {
            "count": 0,
            "reports": [],
            "latest_date": None,
            "report_types": defaultdict(int)
        })
        
        for doc in documents:
            company = doc.get("corp_name", "Unknown")
            summary = by_company[company]
            
            summary["count"] += 1
            summary["reports"].append({
                "date": doc.get("rcept_dt", ""),
                "title": doc.get("report_nm", ""),
                "rcept_no": doc.get("rcept_no", "")
            })
            
            # 최신 날짜 업데이트
            doc_date = doc.get("rcept_dt", "")
            if doc_date and (not summary["latest_date"] or doc_date > summary["latest_date"]):
                summary["latest_date"] = doc_date
            
            # 보고서 유형 집계
            if doc.get("report_nm"):
                summary["report_types"][doc["report_nm"]] += 1
        
        # 상위 보고서만 유지
        for company in by_company:
            by_company[company]["reports"] = by_company[company]["reports"][:5]
            by_company[company]["report_types"] = dict(by_company[company]["report_types"])
        
        return dict(by_company)
    
    def _summarize_by_doc_type(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """문서유형별 요약"""
        by_type = defaultdict(lambda: {
            "count": 0,
            "companies": set(),
            "date_range": {"start": None, "end": None},
            "examples": []
        })
        
        for doc in documents:
            doc_type = doc.get("report_nm", "기타")
            summary = by_type[doc_type]
            
            summary["count"] += 1
            
            if doc.get("corp_name"):
                summary["companies"].add(doc["corp_name"])
            
            # 날짜 범위 업데이트
            doc_date = doc.get("rcept_dt", "")
            if doc_date:
                if not summary["date_range"]["start"] or doc_date < summary["date_range"]["start"]:
                    summary["date_range"]["start"] = doc_date
                if not summary["date_range"]["end"] or doc_date > summary["date_range"]["end"]:
                    summary["date_range"]["end"] = doc_date
            
            # 예시 추가 (최대 3개)
            if len(summary["examples"]) < 3:
                summary["examples"].append({
                    "company": doc.get("corp_name", ""),
                    "date": doc_date,
                    "rcept_no": doc.get("rcept_no", "")
                })
        
        # Set을 list로 변환
        for doc_type in by_type:
            by_type[doc_type]["companies"] = list(by_type[doc_type]["companies"])
        
        return dict(by_type)
    
    def _generate_rule_based_answer(
        self,
        query: str,
        analysis: Dict[str, Any],
        key_findings: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]]
    ) -> str:
        """규칙 기반 답변 생성"""
        lines = []
        
        # 전체 요약
        lines.append(f"'{query}'에 대한 검색 결과입니다.\n")
        
        # 기본 통계
        lines.append(f"총 {analysis['total_count']}건의 관련 공시를 찾았습니다.")
        
        if analysis["date_range"]["start"] and analysis["date_range"]["end"]:
            lines.append(f"기간: {analysis['date_range']['start']} ~ {analysis['date_range']['end']}")
        
        if analysis["companies"]:
            companies_str = ", ".join(list(analysis["companies"])[:5])
            lines.append(f"관련 기업: {companies_str}")
        
        # 주요 보고서 유형
        if analysis["report_types"]:
            top_types = sorted(analysis["report_types"].items(), key=lambda x: x[1], reverse=True)[:3]
            types_str = ", ".join([f"{t[0]}({t[1]}건)" for t in top_types])
            lines.append(f"주요 공시 유형: {types_str}")
        
        # 핵심 발견사항
        if key_findings:
            lines.append("\n### 주요 공시:")
            for i, finding in enumerate(key_findings[:3], 1):
                lines.append(f"{i}. [{finding['company']}] {finding['title']} ({finding['date']})")
                if finding.get("summary"):
                    lines.append(f"   - {finding['summary']}")
        
        # 최근 동향
        if timeline and timeline[0]["events"]:
            lines.append("\n### 최근 동향:")
            latest = timeline[0]
            lines.append(f"가장 최근 공시일: {latest['date']} ({latest['count']}건)")
            for event in latest["events"][:2]:
                lines.append(f"- {event['company']}: {event['title']}")
        
        # 키워드 매칭
        if analysis.get("keywords_found"):
            lines.append(f"\n발견된 키워드: {', '.join(analysis['keywords_found'])}")
        
        return "\n".join(lines)
    
    async def _generate_llm_answer(
        self,
        query: str,
        analysis: Dict[str, Any],
        key_findings: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        documents: List[Dict[str, Any]] = None
    ) -> str:
        """LLM을 사용한 답변 생성"""
        # LLM이 설정되지 않은 경우 규칙 기반으로 폴백
        if not self.llm_client:
            return self._generate_rule_based_answer(query, analysis, key_findings, timeline)
        
        try:
            # 프롬프트 구성 (documents 추가)
            prompt = self._create_synthesis_prompt(query, analysis, key_findings, timeline, documents)
            
            # 환경변수에서 모델명 가져오기
            import os
            model_name = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
            
            # LLM 호출
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "당신은 DART 공시 정보를 분석하는 전문가입니다. 공시 문서의 구체적인 내용을 분석하여 정확한 정보를 제공합니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=5000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM synthesis error: {e}")
            # 에러 시 규칙 기반으로 폴백
            return self._generate_rule_based_answer(query, analysis, key_findings, timeline)
    
    def _load_prompt(self) -> str:
        """프롬프트 파일 로드"""
        prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'synthesis.txt'
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load synthesis prompt: {e}")
            # 폴백 프롬프트
            return """다음 DART 공시 검색 결과를 바탕으로 사용자 질의에 대한 답변을 작성해주세요.
사용자 질의: {query}
답변:"""

    def _create_synthesis_prompt(
        self,
        query: str,
        analysis: Dict[str, Any],
        key_findings: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        documents: List[Dict[str, Any]] = None
    ) -> str:
        """LLM용 프롬프트 생성"""
        # 상위 문서 내용 포맷팅
        document_contents = ""
        if documents:
            for i, doc in enumerate(documents[:5], 1):  # 상위 5개 문서
                doc_content = f"\n### 문서 {i}\n"
                doc_content += f"- **기업**: {doc.get('corp_name', 'N/A')}\n"
                doc_content += f"- **제목**: {doc.get('report_nm', 'N/A')}\n"
                doc_content += f"- **공시일**: {doc.get('rcept_dt', 'N/A')}\n"
                doc_content += f"- **접수번호**: {doc.get('rcept_no', 'N/A')}\n"
                
                # 문서 내용이 있으면 포함
                if doc.get('content'):
                    content = doc['content']
                    # 너무 길면 잘라내기 (각 문서당 최대 1500자)
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    doc_content += f"\n**내용**:\n```\n{content}\n```\n"
                
                # 구조화된 데이터가 있으면 포함
                if doc.get('structured_data'):
                    doc_content += f"\n**구조화 데이터**:\n"
                    for key, value in doc['structured_data'].items():
                        if value:
                            doc_content += f"- {key}: {value}\n"
                
                document_contents += doc_content
        
        prompt = self.synthesis_prompt.format(
            query=query,
            total_count=analysis['total_count'],
            date_start=analysis['date_range']['start'],
            date_end=analysis['date_range']['end'],
            companies=', '.join(list(analysis['companies'])[:5]),
            avg_relevance=f"{analysis['avg_relevance']:.1f}",
            document_contents=document_contents if document_contents else "문서 내용 없음",
            key_findings=json.dumps(key_findings[:3], ensure_ascii=False, indent=2),
            timeline=json.dumps(timeline[:3], ensure_ascii=False, indent=2)
        )
        
        return prompt
    
    def _format_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """문서 포맷팅"""
        formatted = []
        
        for doc in documents:
            formatted_doc = {
                "index": doc.get("index", 0),
                "company": doc.get("corp_name", ""),
                "title": doc.get("report_nm", ""),
                "date": doc.get("rcept_dt", ""),
                "submitter": doc.get("flr_nm", ""),
                "rcept_no": doc.get("rcept_no", ""),
                "url": self._generate_dart_url(doc.get("rcept_no"))
            }
            
            # 문서 내용과 소스 정보 추가
            if doc.get("content"):
                # LLM용으로 내용 정리 (최대 5000자)
                formatted_doc["content"] = clean_for_llm(doc["content"], max_length=2000)
            if doc.get("source"):
                formatted_doc["source"] = doc["source"]
            if doc.get("structured_data"):
                formatted_doc["structured_data"] = doc["structured_data"]
                
            formatted.append(formatted_doc)
        
        return formatted
    
    def _generate_dart_url(self, rcept_no: str) -> str:
        """DART 뷰어 URL 생성"""
        if not rcept_no:
            return ""
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"