#!/usr/bin/env python3
"""Update the static astronomy curation page without paid APIs.

The script is intentionally conservative: it uses public RSS/API endpoints,
keeps the existing design/JS behavior, and falls back to the current page if a
source is temporarily unavailable.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
INDEX = OUTPUTS / "index.html"
ASTRONOMY_NEWS = OUTPUTS / "astronomy-news.html"
SERVICE_WORKER = OUTPUTS / "service-worker.js"
KST = dt.timezone(dt.timedelta(hours=9), "KST")


MONTHLY_TOPICS = {
    1: ["생일별자리", "황도 12궁", "작용 반작용", "로켓의 원리", "비행기의 원리", "우주 탐사", "화성 탐사", "지구탈출속도", "분광", "흡수선", "분광형", "프라운호퍼선"],
    2: ["달 형성 과정", "달의 역사", "우주인의 조건", "국제우주정거장", "흑체복사곡선", "분광형", "별의 색깔", "별의 표면온도", "인공위성", "자이로스코프"],
    3: ["빛공해", "히파르코스", "별의 일생", "중력", "만유인력", "4원소설", "뉴턴", "아인슈타인", "중력장"],
    4: ["갈릴레오 갈릴레이", "태양", "홍염", "플레어", "코로나", "태양풍", "흑점", "오로라", "일식", "달의 위상", "달의 물리적 특징", "동주기자전", "칭동", "달 형성 과정", "천문단위", "광년", "파섹", "우주거리사다리", "적색편이"],
    5: ["북극성", "태양계", "행성", "변광성"],
    6: ["견우와 직녀", "별의 크기", "가장 큰 별", "가장 작은 별", "지구 자전과 공전", "계절별자리", "HR도"],
    7: ["별자리의 정의", "IAU 공식 별자리", "은하수", "우리은하 구조와 특징", "허셜", "섀플리", "혜성", "유성", "유성우", "3대 유성우", "카이퍼벨트", "오르트구름", "운석", "블랙홀", "사건의 지평선", "슈바르츠실트 반지름", "특이점", "블랙홀 그림자", "페르세우스자리 유성우"],
    8: ["일식", "자외선", "달탐사", "아폴로 계획", "우주경쟁", "뉴스페이스시대", "소행성", "왜행성", "티티우스-보데 법칙", "행성의 조건", "빛의 속도"],
    9: ["동서양 별자리 기원", "광년", "고유운동", "망원경", "색수차", "상대성", "관성계", "특수상대성이론", "일반상대성이론"],
    10: ["성운", "성단", "공룡", "소행성 충돌", "이리듐", "칙솔루브 크레이터", "근지구천체", "운석", "화석", "메시에", "메시에 목록", "은하", "전파천문학", "방출스펙트럼", "퀘이사", "활동은하핵", "적색편이", "허블상수", "허블-르메트르의 법칙"],
    11: ["별똥별", "3대 유성우", "쌍둥이자리 유성우", "지구", "세차운동", "앙부일구", "외부은하", "커티스-섀플리 대논쟁", "우리은하", "안드로메다은하", "허블 분류", "허블-르메트르 법칙", "정상우주론", "빅뱅우주론", "급팽창우주론", "우주배경복사", "우주론"],
    12: ["색-온도 관계", "겉보기등급", "절대등급", "외계생명체", "골디락스존", "외계행성", "사분의자리 유성우"],
}

TOPIC_QUERY = {
    1: ["zodiac", "rocket", "mars", "spectroscopy", "fraunhofer"],
    2: ["moon formation", "international space station", "blackbody", "stellar temperature", "gyroscope"],
    3: ["light pollution", "stellar evolution", "gravity", "newton", "einstein"],
    4: ["sun", "solar flare", "corona", "aurora", "eclipse", "redshift"],
    5: ["polaris", "solar system", "planet", "variable star"],
    6: ["stellar radius", "largest star", "smallest star", "seasonal constellations", "Hertzsprung Russell"],
    7: ["constellation", "milky way", "meteor shower", "black hole", "event horizon"],
    8: ["eclipse", "ultraviolet", "moon mission", "asteroid", "dwarf planet"],
    9: ["proper motion", "telescope", "chromatic aberration", "special relativity", "general relativity"],
    10: ["nebula", "star cluster", "near earth object", "meteorite", "quasar", "hubble constant"],
    11: ["meteor shower", "precession", "andromeda", "hubble classification", "cosmic microwave background"],
    12: ["stellar color temperature", "absolute magnitude", "exoplanet", "habitable zone", "quadrantids"],
}

NEWS_FEEDS = [
    "https://science.nasa.gov/feed/",
    "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
    "https://www.nasa.gov/news-release/feed/",
]


@dataclass
class Item:
    item_id: str
    title: str
    source: str
    date: str
    url: str
    kind: str
    summary: str
    tags: list[str]
    detail: list[str]


SEED_ITEMS = {
    6: [
        Item(
            "hubble-june",
            "Hubble's Night Sky Challenge: June",
            "NASA Science",
            "2026-02-04",
            "https://science.nasa.gov/mission/hubble/science/explore-the-night-sky/hubbles-night-sky-challenge-june/",
            "뉴스",
            "허블의 6월 밤하늘 관측 안내는 계절별자리와 실제 관측 대상을 함께 살펴볼 수 있게 정리한 자료입니다. 6월에 보이는 별과 천체를 확인하며 지구의 공전에 따라 밤하늘이 달라지는 점을 연결해 볼 수 있습니다.",
            ["계절별자리", "허블", "밤하늘"],
            [
                "6월 밤하늘에서 관측할 수 있는 천체와 별자리를 중심으로 구성된 허블 자료입니다.",
                "계절에 따라 밤에 보이는 별자리와 관측 대상이 달라진다는 점을 확인할 수 있습니다.",
                "별자리, 밝은 별, 성운·성단 같은 대상을 실제 하늘과 연결해 살펴보는 데 적합합니다.",
                "원문에는 해당 달에 주목할 만한 관측 대상과 설명이 함께 제시됩니다.",
            ],
        ),
        Item(
            "chandra-young-stars",
            "NASA's Chandra Finds Young Stars Dim Quickly",
            "NASA Chandra",
            "2026-04-23",
            "https://www.nasa.gov/image-article/nasas-chandra-finds-young-stars-dim-quickly/",
            "뉴스",
            "찬드라 X선 관측은 젊은 별의 고에너지 방출이 예상보다 빠르게 약해질 수 있음을 보여줍니다. 별의 나이와 활동성 변화는 주변 행성 환경을 해석하는 데 중요한 단서가 됩니다.",
            ["별의활동", "X선", "찬드라"],
            [
                "찬드라 X선 관측을 통해 젊은 별의 고에너지 방출 변화가 분석되었습니다.",
                "X선 방출은 주변 행성 대기와 복사 환경에 영향을 줄 수 있습니다.",
                "젊은 별의 활동성이 시간에 따라 어떻게 줄어드는지 이해하는 데 도움이 됩니다.",
                "별의 물리량과 주변 행성 환경을 함께 해석해야 한다는 점을 보여줍니다.",
            ],
        ),
        Item(
            "pueo-neutrino",
            "New Instrument Used Antarctic Ice Sheet to Probe Extreme Universe",
            "NASA Science",
            "2026-05-26",
            "https://science.nasa.gov/science-research/science-enabling-technology/technology-highlights/new-instrument-used-antarctic-ice-sheet-to-probe-extreme-universe/",
            "최신 뉴스",
            "PUEO 임무는 남극 빙상을 거대한 탐지 매질처럼 활용해 초고에너지 중성미자를 찾는 관측 장비입니다. 극한 우주 현상을 빛뿐 아니라 입자 신호로 추적하는 현대 천문학의 흐름을 보여줍니다.",
            ["중성미자", "남극빙상", "천체물리"],
            [
                "PUEO는 남극 상공의 장기 체공 풍선과 빙상을 이용해 초고에너지 중성미자를 찾습니다.",
                "초고에너지 중성미자는 블랙홀 주변이나 감마선 폭발 같은 극한 천체 현상의 단서가 될 수 있습니다.",
                "빛으로 직접 보기 어려운 현상을 입자 신호로 추적한다는 점이 핵심입니다.",
                "지구 환경과 우주 관측 장비를 결합한 다중신호 천문학 사례입니다.",
            ],
        ),
    ]
}


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "mongmong-astronomy-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def clean_id(value: str) -> str:
    value = re.sub(r"https?://", "", value.lower())
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:54] or "astronomy-item"


def sentence_summary(text: str, max_sentences: int = 3) -> str:
    text = strip_html(text)
    if not text:
        return "원문 설명을 바탕으로 핵심 내용을 확인할 수 있는 천문학 항목입니다."
    parts = re.split(r"(?<=[.!?])\s+", text)
    picked = [part.strip() for part in parts if part.strip()][:max_sentences]
    return " ".join(picked)[:520].strip()


def korean_summary(title: str, source_text: str, tags: list[str], kind: str) -> str:
    tag_text = "·".join(tags[:2]) if tags else "천문학"
    topic_phrase = f"{tag_text} 관련"
    source_text = strip_html(source_text)
    if "논문" in kind:
        return (
            f"이 논문은 '{title}'를 중심으로 {topic_phrase} 천문 현상을 다룹니다. "
            "초록에서 제시한 관측 자료와 분석 방법을 바탕으로 핵심 결과를 확인할 수 있습니다. "
            "원문에서는 연구 배경, 자료 처리, 결론을 더 자세히 볼 수 있습니다."
        )
    if source_text:
        return (
            f"이 소식은 '{title}'와 관련된 최근 천문학·우주과학 내용을 전합니다. "
            f"핵심 주제는 {tag_text}이고, 원문 설명을 통해 관측 대상이나 임무의 의미를 확인할 수 있습니다. "
            "자세한 배경과 기관의 공식 설명은 원문에서 이어서 볼 수 있습니다."
        )
    return f"이 항목은 '{title}'와 관련된 천문학 소식입니다. 핵심 주제는 {tag_text}입니다."


def korean_detail(title: str, source_text: str, tags: list[str], kind: str) -> list[str]:
    tag_text = ", ".join(tags[:3]) if tags else "천문학"
    excerpt = sentence_summary(source_text, 2)
    lines = [
        f"제목 기준으로 이 항목은 {tag_text}와 직접 연결됩니다.",
        "공식 원문 또는 초록에서 날짜, 링크, 출처를 확인할 수 있는 항목만 사용합니다.",
    ]
    if excerpt:
        lines.append(f"원문 핵심 문장: {excerpt}")
    if "논문" in kind:
        lines.extend([
            "논문 초록은 연구 대상, 사용한 자료, 분석 방향을 요약해 줍니다.",
            "자세한 수치, 표본, 결론은 논문 원문에서 확인하는 구조입니다.",
        ])
    else:
        lines.extend([
            "뉴스 본문은 관측 결과나 임무의 배경을 대중적으로 정리합니다.",
            "공식 기관 발표를 우선 사용해 링크와 날짜 추적이 가능하도록 했습니다.",
        ])
    return lines[:6]


def parse_rss_date(value: str) -> str:
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.date().isoformat()
    except Exception:
        return dt.datetime.now(KST).date().isoformat()


def read_existing_items() -> dict[str, Item]:
    text = INDEX.read_text(encoding="utf-8")
    detail_match = re.search(r"const detailData = (\{.*?\});\n\n    const modal", text, re.S)
    detail_data = {}
    if detail_match:
        try:
            detail_data = json.loads(detail_match.group(1))
        except json.JSONDecodeError:
            detail_data = {}

    items: dict[str, Item] = {}
    article_re = re.compile(
        r'<article class="item" data-item-id="(?P<id>[^"]+)" data-origin-view="(?P<origin>[^"]+)">.*?'
        r'<span class="label[^"]*">(?P<label>[^<]+)</span><span>(?P<source>[^<]+)</span><time datetime="(?P<date>[^"]+)">[^<]+</time>.*?'
        r"<h3>(?P<title>.*?)</h3>\s*<p>(?P<summary>.*?)</p>.*?"
        r'<div class="tags">(?P<tags>.*?)</div>.*?'
        r'<a class="readmore" href="(?P<url>[^"]+)"',
        re.S,
    )
    for match in article_re.finditer(text):
        tags = re.findall(r'<span class="tag">#?([^<]+)</span>', match.group("tags"))
        detail = detail_data.get(match.group("id"), {}).get("summary", [])
        items[match.group("id")] = Item(
            item_id=match.group("id"),
            title=strip_html(match.group("title")),
            source=strip_html(match.group("source")),
            date=match.group("date"),
            url=html.unescape(match.group("url")),
            kind=strip_html(match.group("label")),
            summary=strip_html(match.group("summary")),
            tags=tags[:3] or ["천문학", "우주", "관측"],
            detail=detail[:6] if isinstance(detail, list) else [],
        )
    return items


def fetch_news() -> list[Item]:
    items: list[Item] = []
    for feed in NEWS_FEEDS:
        try:
            root = ET.fromstring(fetch_text(feed))
        except Exception:
            continue
        source = root.findtext("./channel/title") or urllib.parse.urlparse(feed).netloc
        for node in root.findall("./channel/item"):
            title = strip_html(node.findtext("title") or "")
            url = strip_html(node.findtext("link") or "")
            description = strip_html(node.findtext("description") or "")
            pub_date = parse_rss_date(node.findtext("pubDate") or "")
            if not title or not url:
                continue
            text = f"{title} {description}".lower()
            if any(key in text for key in ["contract", "awards contract", "headquarters", "public event", "media accreditation", "administrator"]):
                continue
            if not any(key in text for key in ["space", "astronom", "planet", "star", "galaxy", "solar", "moon", "asteroid", "telescope", "cosmic", "hubble", "webb", "chandra", "exoplanet", "comet", "meteor"]):
                continue
            tags = choose_tags(f"{title} {description}")
            items.append(Item(
                item_id=clean_id(url),
                title=title,
                source=strip_html(source).replace(" - NASA", ""),
                date=pub_date,
                url=url,
                kind="뉴스",
                summary=korean_summary(title, description, tags, "뉴스"),
                tags=tags,
                detail=korean_detail(title, description, tags, "뉴스"),
            ))
    return unique_by_url(items)


def arxiv_query(search: str, max_results: int = 12) -> list[Item]:
    params = urllib.parse.urlencode({
        "search_query": search,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"https://export.arxiv.org/api/query?{params}"
    try:
        root = ET.fromstring(fetch_text(url))
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items: list[Item] = []
    for entry in root.findall("a:entry", ns):
        title = strip_html(entry.findtext("a:title", default="", namespaces=ns))
        summary = strip_html(entry.findtext("a:summary", default="", namespaces=ns))
        published = entry.findtext("a:published", default="", namespaces=ns)[:10]
        link = entry.findtext("a:id", default="", namespaces=ns)
        if not title or not link:
            continue
        tags = choose_tags(f"{title} {summary}")
        items.append(Item(
            item_id=clean_id(link),
            title=title,
            source="arXiv",
            date=published or dt.datetime.now(KST).date().isoformat(),
            url=link,
            kind="논문",
            summary=korean_summary(title, summary, tags, "논문"),
            tags=tags,
            detail=korean_detail(title, summary, tags, "논문"),
        ))
    return items


def unique_by_url(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    result: list[Item] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        result.append(item)
    return result


def choose_tags(text: str) -> list[str]:
    text_l = text.lower()
    mapping = [
        ("gravitational wave", "중력파"), ("gravity wave", "중력파"),
        ("black hole", "블랙홀"), ("event horizon", "사건의지평선"), ("meteor", "유성"),
        ("exoplanet", "외계행성"), ("habitable", "골디락스존"), ("solar", "태양"),
        ("moon", "달"), ("lunar", "달"), ("star", "별"), ("stellar", "별"),
        ("galaxy", "은하"), ("milky way", "우리은하"), ("telescope", "망원경"),
        ("spectrum", "분광"), ("spectros", "분광"), ("asteroid", "소행성"),
        ("comet", "혜성"), ("nebula", "성운"), ("cluster", "성단"),
        ("redshift", "적색편이"), ("cosmology", "우주론"), ("planet", "행성"),
        ("constellation", "별자리"), ("hertzsprung", "HR도"), ("radius", "반지름"),
        ("supernova", "초신성"), ("neutrino", "중성미자"),
    ]
    tags: list[str] = []
    for key, tag in mapping:
        if key in text_l and tag not in tags:
            tags.append(tag)
        if len(tags) == 3:
            return tags
    for fallback in ["천문학", "우주", "관측"]:
        if fallback not in tags:
            tags.append(fallback)
        if len(tags) == 3:
            break
    return tags


def detail_lines(text: str, title: str) -> list[str]:
    summary = sentence_summary(text, 6)
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", summary) if part.strip()]
    lines = parts[:5]
    while len(lines) < 4:
        lines.append(f"'{title}' 항목은 원문에서 제시한 관측·분석 내용을 중심으로 확인할 수 있습니다.")
    return lines[:6]


def score_interest(item: Item, month: int) -> int:
    haystack = f"{item.title} {item.summary} {' '.join(item.tags)}".lower()
    return sum(1 for key in TOPIC_QUERY[month] if key.lower() in haystack)


def build_items(month: int, existing: dict[str, Item]) -> tuple[list[Item], list[Item], dict[str, Item]]:
    news = fetch_news()
    seed = deepcopy(SEED_ITEMS.get(month, []))
    paper_query = " OR ".join(f'all:"{term}"' for term in TOPIC_QUERY[month][:5])
    interest_papers = arxiv_query(f"cat:astro-ph* AND ({paper_query})", 16)
    latest_papers = arxiv_query("cat:astro-ph*", 8)

    interest_news = [item for item in news if score_interest(item, month) > 0]
    if len(interest_news) < 2:
        interest_news.extend(item for item in seed if item.kind == "뉴스" and item.url not in {news_item.url for news_item in interest_news})

    selected_interest = unique_by_url(interest_news)[:2] + unique_by_url(interest_papers)[:2]
    used_urls = {item.url for item in selected_interest}
    latest_news = [item for item in news if item.url not in used_urls]
    if not latest_news:
        latest_news = [item for item in seed if item.url not in used_urls]
    selected_latest = unique_by_url(latest_news)[:1] + [item for item in latest_papers if item.url not in used_urls][:1]

    fallback_order = seed + list(existing.values())
    while len(selected_interest) < 4 and fallback_order:
        candidate = deepcopy(fallback_order.pop(0))
        if candidate.url not in {i.url for i in selected_interest}:
            selected_interest.append(candidate)
    while len(selected_latest) < 2 and fallback_order:
        candidate = deepcopy(fallback_order.pop(0))
        if candidate.url not in {i.url for i in selected_interest + selected_latest}:
            selected_latest.append(candidate)

    selected_interest = deepcopy(selected_interest[:4])
    selected_latest = deepcopy(selected_latest[:2])
    for item in selected_interest[:2]:
        item.kind = "뉴스"
    for item in selected_interest[2:4]:
        item.kind = "논문"
    if selected_latest:
        selected_latest[0].kind = "최신 뉴스"
    if len(selected_latest) > 1:
        selected_latest[1].kind = "최신 논문"
    return selected_interest, selected_latest, existing


def article_html(item: Item, origin: str) -> str:
    label_class = "latest" if "최신" in item.kind else "paper" if "논문" in item.kind else ""
    label_attr = f' class="label {label_class}"' if label_class else ' class="label"'
    button_text = "논문 보기" if "논문" in item.kind else "원문 보기"
    tags = "".join(f'<span class="tag">#{html.escape(tag)}</span>' for tag in item.tags[:3])
    return textwrap.dedent(f"""\
          <article class="item" data-item-id="{html.escape(item.item_id)}" data-origin-view="{origin}">
            <div class="item-main">
              <div class="meta"><span{label_attr}>{html.escape(item.kind)}</span><span>{html.escape(item.source)}</span><time datetime="{html.escape(item.date)}">{html.escape(item.date)}</time></div>
              <h3>{html.escape(item.title)}</h3>
              <p>{html.escape(item.summary)}</p>
            </div>
            <div class="item-side">
              <div class="tags">{tags}</div>
              <div class="actions">
                <a class="readmore" href="{html.escape(item.url)}" target="_blank" rel="noopener noreferrer">{button_text}</a>
                <button type="button" class="detail-button" data-detail="{html.escape(item.item_id)}">상세 요약</button>
                <button type="button" class="like-button" aria-label="보관함에 추가" aria-pressed="false">♡</button>
              </div>
            </div>
          </article>""")


def detail_json(items: list[Item]) -> str:
    data = {
        item.item_id: {
            "title": item.title,
            "meta": f"{item.source} · {item.date} · {item.kind}",
            "summary": item.detail[:6],
        }
        for item in items
    }
    return json.dumps(data, ensure_ascii=False, indent=6)


def update_html(text: str, interest: list[Item], latest: list[Item], now: dt.datetime) -> str:
    month = now.month
    topics = MONTHLY_TOPICS[month][:7]
    topic_html = "\n".join(f'          <span class="topic">{html.escape(topic)}</span>' for topic in topics)
    interest_html = "\n\n".join(article_html(item, "interest") for item in interest)
    latest_html = "\n\n".join(article_html(item, "latest") for item in latest)

    text = re.sub(r"<span class=\"pill\">\d{4}년 \d+월</span>", f'<span class="pill">{now.year}년 {month}월</span>', text)
    text = re.sub(r"<span class=\"pill\">업데이트: .*?</span>", f'<span class="pill">업데이트: {now:%Y-%m-%d %H:%M} KST</span>', text)
    text = re.sub(r"<h2>\d+월 관심 주제</h2>", f"<h2>{month}월 관심 주제</h2>", text)
    text = re.sub(r'<div class="topics">.*?</div>', f'<div class="topics">\n{topic_html}\n        </div>', text, count=1, flags=re.S)

    text = re.sub(
        r'(<section class="section" id="interest">.*?<div class="feed">\n).*?(\n        </div>\n      </section>\n\n      <section class="section" id="latest" hidden>)',
        lambda match: match.group(1) + interest_html + match.group(2),
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r'(<section class="section" id="latest" hidden>.*?<div class="feed">\n).*?(\n        </div>\n      </section>\n\n      <section class="section" id="archive" hidden>)',
        lambda match: match.group(1) + latest_html + match.group(2),
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(r"const detailData = \{.*?\};\n\n    const modal", f"const detailData = {detail_json(interest + latest)};\n\n    const modal", text, count=1, flags=re.S)
    return text


def bump_cache() -> None:
    text = SERVICE_WORKER.read_text(encoding="utf-8")
    match = re.search(r'mongmong-astronomy-v(\d+)', text)
    if not match:
        return
    version = int(match.group(1)) + 1
    SERVICE_WORKER.write_text(re.sub(r'mongmong-astronomy-v\d+', f"mongmong-astronomy-v{version}", text, count=1), encoding="utf-8")


def main() -> None:
    now = dt.datetime.now(KST).replace(second=0, microsecond=0)
    existing = read_existing_items()
    interest, latest, _ = build_items(now.month, existing)
    original = INDEX.read_text(encoding="utf-8")
    updated = update_html(original, interest, latest, now)
    if updated != original:
        INDEX.write_text(updated, encoding="utf-8", newline="\n")
        ASTRONOMY_NEWS.write_text(updated, encoding="utf-8", newline="\n")
        bump_cache()
        print("Updated astronomy curation page.")
    else:
        print("No page changes.")


if __name__ == "__main__":
    main()
