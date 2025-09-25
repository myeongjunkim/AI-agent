from typing import List
from app.tools.base import BaseTool
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from lxml import html # type: ignore
import queue
import threading
import asyncio
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor


class WebDriverPool:
    """WebDriver 인스턴스 풀 관리"""
    
    def __init__(self, pool_size: int = 4):
        self.pool_size = pool_size
        self.pool: queue.Queue[webdriver.Chrome]  = queue.Queue(maxsize=pool_size)
        self.chrome_options = self._setup_chrome_options()
        self._initialize_pool()
    
    def _setup_chrome_options(self) -> Options:
        """Chrome 옵션 설정"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return options
    
    def _initialize_pool(self):
        """WebDriver 풀 초기화"""
        print(f"Initializing WebDriver pool with {self.pool_size} instances...")
        for i in range(self.pool_size):
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.pool.put(driver)
            print(f"WebDriver {i+1}/{self.pool_size} initialized")
    
    @contextmanager
    def get_driver(self):
        """WebDriver를 풀에서 가져오고 사용 후 반환"""
        driver = self.pool.get()
        try:
            yield driver
        finally:
            self.pool.put(driver)
    
    def close_all(self):
        """모든 WebDriver 종료"""
        print("Closing all WebDriver instances...")
        while not self.pool.empty():
            driver = self.pool.get()
            driver.quit()
        print("All WebDriver instances closed")


class MultipleUrlDetailTool(BaseTool):
    """WebDriver 풀을 사용한 최적화된 URL 상세 정보 도구"""

    def __init__(self, pool_size: int = 4):
        self.driver_pool = WebDriverPool(pool_size=pool_size)
        self.max_workers = pool_size

    async def execute(self, urls: List[str]) -> List[str]:
        """WebDriver 풀을 사용한 병렬 처리"""
        print(f"Processing {len(urls)} URLs with {self.max_workers} workers...")
        
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                loop = asyncio.get_event_loop()
                tasks = [
                    loop.run_in_executor(executor, self._fetch_single_url_pooled, url)
                    for url in urls
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 예외 처리 및 결과 정리
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Error processing URL {i+1}: {result}")
                    final_results.append(f"Error: {str(result)}")
                else:
                    final_results.append(result) # type: ignore
                    
            return final_results
            
        finally:
            # 모든 WebDriver 종료
            self.driver_pool.close_all()

    def _fetch_single_url_pooled(self, url: str) -> str:
        """풀에서 WebDriver를 가져와서 사용"""
        thread_name = threading.current_thread().name
        try:
            with self.driver_pool.get_driver() as driver:
                print(f"[{thread_name}] Fetching: {url}")
                driver.get(url)
                # 페이지 로딩 대기 시간 단축 및 조건 완화
                try:
                    WebDriverWait(driver, 5).until(  # 10초 → 5초
                        lambda d: d.execute_script("return document.readyState") in ["interactive", "complete"]
                    )
                except Exception as e:
                    print(f"[{thread_name}] Timeout fetching {url}: {e}")
                    pass  # 타임아웃되어도 계속 진행
                
                final_url = driver.current_url
                page_source = driver.page_source
                
                print(f"[{thread_name}] Original: {url}")
                print(f"[{thread_name}] Final: {final_url}")
                
                tree = html.fromstring(page_source)
                text_content = self._extract_simple_content(tree)
                
                return f"URL: {final_url}\n\n{text_content}"
                
        except Exception as e:
            print(f"[{thread_name}] Error fetching {url}: {str(e)}")
            return f"Error fetching {url}: {str(e)}"

    def _extract_simple_content(self, tree: html.HtmlElement) -> str:
        """페이지에서 주요 텍스트 내용 추출"""
        
        for tag in tree.xpath('//script | //style | //nav | //footer | //aside'):
            if tag.getparent() is not None:
                tag.getparent().remove(tag)
        
        body = tree.xpath('//body')[0] if tree.xpath('//body') else tree
        text = body.text_content()
        
        clean_text = ' '.join(text.split())
        
        if len(clean_text) > 2000:
            return clean_text[:2000] + "..."
        
        return clean_text