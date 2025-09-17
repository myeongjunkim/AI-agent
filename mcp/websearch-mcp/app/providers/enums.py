from __future__ import annotations

from enum import Enum


class Channel(str, Enum):
    web = "web"
    news = "news"
    blog = "blog"


class ProviderName(str, Enum):
    google_cse = "google_cse"
    google_news_rss = "google_news_rss"
    naver_web = "naver_web"
    naver_news = "naver_news"
    naver_blog = "naver_blog"


