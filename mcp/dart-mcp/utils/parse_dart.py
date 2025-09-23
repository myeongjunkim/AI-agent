"""
DART document parsing utilities
"""

import asyncio
import json
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from collections import defaultdict
import httpx
from bs4 import BeautifulSoup
from .logging import get_logger

logger = get_logger("dart-mcp.parse")


def _extract_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """HTML에서 메타데이터 추출"""
    metadata = {}
    
    # meta 태그에서 정보 추출
    for meta in soup.find_all('meta'):
        name = meta.get('name', '') or meta.get('property', '')
        content = meta.get('content', '')
        if name and content:
            metadata[name] = content
    
    # DART 특화 메타데이터
    meta_selectors = {
        '공시일자': ['span.date', 'div.rcept_dt'],
        '회사명': ['span.corp_name', 'div.corp_name'],
        '보고서명': ['span.report_nm', 'div.report_nm'],
        '제출인': ['span.flr_nm', 'div.flr_nm']
    }
    
    for key, selectors in meta_selectors.items():
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                metadata[key] = elem.get_text(strip=True)
                break
    
    return metadata


def _extract_financial_data(soup: BeautifulSoup) -> Dict[str, Any]:
    """재무 데이터 추출"""
    financial_data = {
        'statements': [],
        'key_metrics': {},
        'currency': 'KRW'
    }
    
    # 재무제표 테이블 찾기
    financial_keywords = ['자산', '부채', '자본', '매출', '영업이익', '당기순이익']
    tables = soup.find_all('table')
    
    for table in tables:
        table_text = table.get_text()
        if any(keyword in table_text for keyword in financial_keywords):
            # 테이블 파싱
            headers = []
            rows = []
            
            for tr in table.find_all('tr'):
                cells = tr.find_all(['th', 'td'])
                if not headers and cells:
                    headers = [cell.get_text(strip=True) for cell in cells]
                elif cells:
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    rows.append(dict(zip(headers, row_data)))
            
            if rows:
                financial_data['statements'].append({
                    'headers': headers,
                    'data': rows
                })
    
    # 주요 지표 추출
    for keyword in financial_keywords:
        for table in tables:
            cells = table.find_all(['td', 'th'])
            for i, cell in enumerate(cells):
                if keyword in cell.get_text():
                    # 다음 셀에서 값 추출
                    if i + 1 < len(cells):
                        value_text = cells[i + 1].get_text(strip=True)
                        # 숫자 추출
                        numbers = re.findall(r'[\d,]+', value_text)
                        if numbers:
                            financial_data['key_metrics'][keyword] = numbers[0]
    
    return financial_data


def _extract_key_entities(text: str) -> Dict[str, List[str]]:
    """텍스트에서 주요 엔티티 추출"""
    entities = {
        'companies': [],
        'dates': [],
        'amounts': [],
        'percentages': [],
        'people': [],
        'products': []
    }
    
    # 회사명 패턴
    company_pattern = r'(?:주식회사\s*)?([가-힣]+(?:전자|화학|물산|건설|제약|바이오|테크|엔터|미디어|금융|증권|은행|보험|카드|캐피탈|자산운용|투자|그룹|홀딩스))'
    companies = re.findall(company_pattern, text)
    entities['companies'] = list(set(companies))
    
    # 날짜 패턴
    date_patterns = [
        r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',
        r'\d{4}\.\d{1,2}\.\d{1,2}',
        r'\d{4}-\d{1,2}-\d{1,2}'
    ]
    for pattern in date_patterns:
        dates = re.findall(pattern, text)
        entities['dates'].extend(dates)
    entities['dates'] = list(set(entities['dates']))
    
    # 금액 패턴
    amount_pattern = r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:원|억원|백만원|천원|달러|USD|KRW)'
    amounts = re.findall(amount_pattern, text)
    entities['amounts'] = list(set(amounts))
    
    # 퍼센트 패턴
    percent_pattern = r'(\d+(?:\.\d+)?)\s*[%％]'
    percentages = re.findall(percent_pattern, text)
    entities['percentages'] = list(set(percentages))
    
    # 인명 패턴 (대표이사, 이사 등)
    person_pattern = r'(?:대표이사|이사|감사|사장|부사장|전무|상무|이사회\s*의장)\s*([가-힣]{2,4})'
    people = re.findall(person_pattern, text)
    entities['people'] = list(set(people))
    
    return entities


def _extract_tables_advanced(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """고급 테이블 추출 및 분석"""
    tables_data = []
    
    tables = soup.find_all('table')
    for idx, table in enumerate(tables):
        table_info = {
            'index': idx,
            'headers': [],
            'rows': [],
            'type': 'unknown',
            'summary': ''
        }
        
        # 헤더 추출
        header_rows = table.find_all('thead')
        if header_rows:
            for tr in header_rows[0].find_all('tr'):
                headers = [th.get_text(strip=True) for th in tr.find_all(['th', 'td'])]
                if headers:
                    table_info['headers'] = headers
        else:
            # thead가 없으면 첫 번째 tr을 헤더로 간주
            first_tr = table.find('tr')
            if first_tr:
                headers = [cell.get_text(strip=True) for cell in first_tr.find_all(['th', 'td'])]
                table_info['headers'] = headers
        
        # 데이터 행 추출
        tbody = table.find('tbody') or table
        for tr in tbody.find_all('tr')[1 if not header_rows else 0:]:
            row_data = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if row_data:
                table_info['rows'].append(row_data)
        
        # 테이블 타입 추론
        table_text = table.get_text()
        if any(keyword in table_text for keyword in ['자산', '부채', '자본']):
            table_info['type'] = 'financial_position'
        elif any(keyword in table_text for keyword in ['매출', '영업이익', '당기순이익']):
            table_info['type'] = 'income_statement'
        elif any(keyword in table_text for keyword in ['주주', '지분', '소유']):
            table_info['type'] = 'shareholders'
        elif any(keyword in table_text for keyword in ['이사', '임원', '감사']):
            table_info['type'] = 'executives'
        
        # 요약 생성
        if table_info['headers'] and table_info['rows']:
            table_info['summary'] = f"테이블 {idx+1}: {len(table_info['headers'])}개 컬럼, {len(table_info['rows'])}개 행"
        
        tables_data.append(table_info)
    
    return tables_data


def _extract_sections(soup: BeautifulSoup) -> Dict[str, str]:
    """문서를 섹션별로 구분하여 추출"""
    sections = {}
    
    # 헤딩 태그 기반 섹션 분리
    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    
    for heading in headings:
        section_title = heading.get_text(strip=True)
        section_content = []
        
        # 다음 헤딩까지의 컨텐츠 수집
        current = heading.find_next_sibling()
        while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            if current.name in ['p', 'div', 'span', 'table', 'ul', 'ol']:
                text = current.get_text(strip=True)
                if text:
                    section_content.append(text)
            current = current.find_next_sibling()
        
        if section_content:
            sections[section_title] = '\n'.join(section_content)
    
    return sections


def _extract_dart_document_content(soup: BeautifulSoup, url: str) -> str:
    """
    DART 문서의 내용을 구조화하여 추출합니다.
    """
    content_parts = []
    
    # 추가 메타데이터 추출
    metadata = _extract_metadata(soup)
    if metadata:
        content_parts.append("[메타데이터]")
        for key, value in metadata.items():
            content_parts.append(f"{key}: {value}")
        content_parts.append("-" * 50)
    
    # 제목 추출
    title_elem = soup.find('title')
    if title_elem:
        content_parts.append(f"제목: {title_elem.text.strip()}")
        content_parts.append("-" * 50)
    
    # 메인 컨텐츠 영역 찾기
    main_content = None
    
    # 다양한 DART 컨텐츠 컨테이너 시도
    content_selectors = [
        'div.contents',
        'div#content',
        'div.report_content',
        'div.view_cont',
        'div.view_content',
        'div.doc_content',
        'div.document',
        'body'
    ]
    
    for selector in content_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    if not main_content:
        main_content = soup.body or soup
    
    # 테이블 처리
    tables = main_content.find_all('table')
    for i, table in enumerate(tables, 1):
        content_parts.append(f"\n[표 {i}]")
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if cells:
                row_text = ' | '.join(cell.get_text(strip=True) for cell in cells)
                content_parts.append(row_text)
        content_parts.append("")
    
    # 텍스트 컨텐츠 추출
    for elem in main_content.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        # 테이블 내부 요소는 이미 처리했으므로 건너뜀
        if elem.find_parent('table'):
            continue
            
        text = elem.get_text(strip=True)
        if text and len(text) > 10:  # 의미있는 텍스트만
            # 헤딩 태그는 구분
            if elem.name.startswith('h'):
                content_parts.append(f"\n[{elem.name.upper()}] {text}")
            else:
                content_parts.append(text)
    
    # 중복 제거 및 정리
    seen = set()
    unique_parts = []
    for part in content_parts:
        if part not in seen and part.strip():
            seen.add(part)
            unique_parts.append(part)
    
    return '\n'.join(unique_parts)

async def parse_dart_url_content(url: str) -> str:
    """
    DART viewer URL의 실제 내용을 파싱하여 구조화된 텍스트로 반환합니다.
    
    Args:
        url: DART viewer URL (예: 'http://dart.fss.or.kr/report/viewer.do?rcpNo=...')
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            }
            
            logger.info(f"Parsing DART URL: {url}")
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # 인코딩 처리
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # DART 특화 파싱
            content = _extract_dart_document_content(soup, url)
            
            return json.dumps({
                "url": url,
                "content": content,
                "success": True
            }, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error parsing DART URL: {e}")
        return json.dumps({
            "url": url,
            "error": str(e),
            "success": False
        }, ensure_ascii=False)

async def parse_multiple_dart_urls(urls: str) -> str:
    """
    여러 DART URL의 내용을 한번에 파싱합니다.
    
    Args:
        urls: 쉼표 또는 '@'로 구분된 URL 목록
    """
    # URL 목록 파싱
    if '@' in urls:
        url_list = [url.strip() for url in urls.split('@') if url.strip()]
    else:
        url_list = [url.strip() for url in urls.split(',') if url.strip()]
    
    if not url_list:
        return json.dumps({
            "error": "URL 목록이 비어있습니다",
            "success": False
        }, ensure_ascii=False)
    
    logger.info(f"Parsing {len(url_list)} DART URLs")
    
    # 모든 URL을 병렬로 처리
    tasks = [parse_dart_url_content(url) for url in url_list]
    results = await asyncio.gather(*tasks)
    
    # 결과 정리
    parsed_results = []
    for result_str in results:
        try:
            result = json.loads(result_str)
            parsed_results.append(result)
        except:
            parsed_results.append({"error": "결과 파싱 실패", "raw": result_str})
    
    return json.dumps({
        "total_urls": len(url_list),
        "results": parsed_results,
        "success": True
    }, ensure_ascii=False)

async def parse_dart_advanced(url: str) -> str:
    """
    DART URL의 내용을 고급 분석하여 구조화된 정보 반환
    
    Args:
        url: DART viewer URL
        
    Returns:
        고급 분석된 정보 (JSON)
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            }
            
            logger.info(f"Advanced parsing DART URL: {url}")
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # 인코딩 처리
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 기본 내용 추출
            basic_content = _extract_dart_document_content(soup, url)
            
            # 고급 분석
            analysis_result = {
                "url": url,
                "basic_content": basic_content,
                "metadata": _extract_metadata(soup),
                "sections": _extract_sections(soup),
                "tables": _extract_tables_advanced(soup),
                "financial_data": _extract_financial_data(soup),
                "entities": _extract_key_entities(basic_content),
                "analysis_timestamp": datetime.now().isoformat(),
                "success": True
            }
            
            # 주요 인사이트 생성
            insights = []
            
            # 재무 인사이트
            if analysis_result["financial_data"]["key_metrics"]:
                insights.append(f"주요 재무지표 {len(analysis_result['financial_data']['key_metrics'])}개 발견")
            
            # 테이블 인사이트  
            table_types = defaultdict(int)
            for table in analysis_result["tables"]:
                table_types[table["type"]] += 1
            
            for t_type, count in table_types.items():
                if t_type != "unknown":
                    insights.append(f"{t_type} 테이블 {count}개 발견")
            
            # 엔티티 인사이트
            if analysis_result["entities"]["companies"]:
                insights.append(f"관련 기업 {len(analysis_result['entities']['companies'])}개 언급")
            
            if analysis_result["entities"]["amounts"]:
                insights.append(f"금액 정보 {len(analysis_result['entities']['amounts'])}개 포함")
            
            analysis_result["insights"] = insights
            
            return json.dumps(analysis_result, ensure_ascii=False)
            
    except Exception as e:
        logger.error(f"Error in advanced DART parsing: {e}")
        return json.dumps({
            "url": url,
            "error": str(e),
            "success": False
        }, ensure_ascii=False)


async def extract_structured_info_from_documents(
    rcp_no: str,
    info_types: Optional[List[str]] = None,
    dart_reader=None,
    get_document_content_func=None,
    get_sub_documents_func=None,
    get_attached_document_list_func=None
) -> str:
    """
    공시 문서에서 구조화된 정보를 추출합니다.
    
    Args:
        rcp_no: 접수번호
        info_types: 추출할 정보 유형 ['financial', 'business', 'audit', 'all']
        dart_reader: DART reader 인스턴스
        get_document_content_func: 문서 내용 조회 함수
        get_sub_documents_func: 하위 문서 조회 함수
        get_attached_document_list_func: 첨부 문서 목록 조회 함수
    """
    if not info_types:
        info_types = ['all']
    
    extracted_info = {
        "rcp_no": rcp_no,
        "extracted_types": info_types
    }
    
    try:
        # 기본 문서 내용 가져오기
        if get_document_content_func:
            doc_content = await get_document_content_func(rcp_no)
            extracted_info["main_document"] = json.loads(doc_content) if isinstance(doc_content, str) else doc_content
        
        # 첨부 문서 목록 가져오기
        if get_attached_document_list_func:
            attached_docs = await get_attached_document_list_func(rcp_no)
            extracted_info["attached_documents"] = json.loads(attached_docs) if isinstance(attached_docs, str) else attached_docs
        
        # info_types에 따라 특정 정보 추출
        if 'financial' in info_types or 'all' in info_types:
            # 재무 관련 정보 추출 로직
            extracted_info["financial_info"] = "재무정보 추출 (구현 필요)"
        
        if 'business' in info_types or 'all' in info_types:
            # 사업 관련 정보 추출 로직
            extracted_info["business_info"] = "사업정보 추출 (구현 필요)"
        
        if 'audit' in info_types or 'all' in info_types:
            # 감사 관련 정보 추출 로직  
            extracted_info["audit_info"] = "감사정보 추출 (구현 필요)"
        
        return json.dumps(extracted_info, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error extracting structured info: {e}")
        return json.dumps({
            "error": str(e),
            "rcp_no": rcp_no
        }, ensure_ascii=False)