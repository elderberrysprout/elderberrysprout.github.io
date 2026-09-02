#!/usr/bin/env python3
"""Extract Elderberry Sprout content from the Squarespace offline backup."""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag

BACKUP = Path("/home/elderberry/CursorWork/elderberrysprout-backup")
OFFLINE = BACKUP / "offline" / "pages"
IMG_SRC = BACKUP / "assets" / "images"
FILE_SRC = BACKUP / "assets" / "files"
ROOT = Path(__file__).resolve().parents[1]
IMG_DST = ROOT / "assets" / "images"
FILE_DST = ROOT / "assets" / "files"
POSTS = ROOT / "content" / "posts"
PRODUCTS = ROOT / "content" / "products"
DISCONTINUED = ROOT / "content" / "discontinued"
VIDEOS = ROOT / "content" / "videos"
FREEBIES = ROOT / "content" / "freebies"

SKIP_DIR_PARTS = {"tag", "category"}
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def soup_file(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")


def parse_sitemap() -> dict[str, str]:
    raw = (BACKUP / "sitemap.xml").read_text(encoding="utf-8", errors="ignore")
    out: dict[str, str] = {}
    for loc, last in re.findall(
        r"<loc>(https://(?:www\.)?elderberrysprout\.com[^<]*)</loc>\s*"
        r"(?:<changefreq>[^<]*</changefreq>\s*)?"
        r"(?:<priority>[^<]*</priority>\s*)?"
        r"<lastmod>([^<]+)</lastmod>",
        raw,
    ):
        path = urlparse(loc).path.rstrip("/")
        out[path or "/"] = last
    # loc-only fallback
    if not out:
        for loc in re.findall(r"<loc>([^<]+)</loc>", raw):
            path = urlparse(loc).path.rstrip("/")
            out[path or "/"] = "2022-01-01"
    return out


def sanitize_name(name: str) -> str:
    name = unquote(name).replace("+", " ")
    stem, dot, ext = name.rpartition(".")
    if not stem:
        stem, ext = name, ""
        dot = ""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-").lower()
    ext = ext.lower()
    if ext:
        return f"{stem}.{ext}"
    return stem


def copy_image(src_name: str, used: dict[str, str]) -> str | None:
    if src_name in used:
        return used[src_name]
    raw = IMG_SRC / src_name
    if not raw.is_file():
        # try unquoted / plus variants
        alt = IMG_SRC / unquote(src_name.replace("+", " "))
        if alt.is_file():
            raw = alt
        else:
            matches = list(IMG_SRC.glob(src_name.replace("+", "*")))
            if not matches:
                return None
            raw = matches[0]
    dest_name = sanitize_name(raw.name)
    dest = IMG_DST / dest_name
    if dest.exists() and dest.stat().st_size != raw.stat().st_size:
        h = hashlib.md5(raw.name.encode()).hexdigest()[:6]
        dest_name = f"{h}-{dest_name}"
        dest = IMG_DST / dest_name
    if not dest.exists():
        shutil.copy2(raw, dest)
    used[src_name] = dest_name
    return dest_name


def extract_img_name(src: str) -> str | None:
    if not src:
        return None
    src = src.split("?")[0]
    if "assets/images/" in src:
        return unquote(src.split("assets/images/", 1)[1])
    return None


KEEP = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "blockquote", "hr"}


def clean_attrs(el: Tag) -> None:
    for child in el.find_all(True):
        href = child.get("href")
        src = child.get("src")
        alt = child.get("alt")
        child.attrs = {}
        if child.name == "a" and href:
            child["href"] = href
        if child.name in {"img", "iframe"} and src:
            child["src"] = src
        if child.name == "img":
            child["alt"] = alt or ""
            child["loading"] = "lazy"
        if child.name == "iframe":
            child["allowfullscreen"] = True
            child["title"] = "YouTube video"
    href = el.get("href")
    src = el.get("src")
    alt = el.get("alt")
    el.attrs = {}
    if el.name == "a" and href:
        el["href"] = href
    if el.name == "img":
        if src:
            el["src"] = src
        el["alt"] = alt or ""
        el["loading"] = "lazy"


def rewrite_content(node: Tag, used: dict[str, str], page_url: str) -> str:
    for bad in node.find_all(["script", "style", "noscript"]):
        bad.decompose()
    for iframe in node.find_all("iframe"):
        blob = f"{iframe.get('src') or ''} {iframe}"
        if "youtube" not in blob.lower():
            iframe.decompose()

    for img in node.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        name = extract_img_name(src)
        dest = copy_image(name, used) if name else None
        if dest:
            img.attrs = {"src": f"/assets/images/{dest}", "alt": img.get("alt") or "", "loading": "lazy"}
        else:
            img.decompose()

    for a in node.find_all("a"):
        a["href"] = rewrite_href(a.get("href") or "", page_url)

    chunks: list[str] = []
    for el in node.find_all(list(KEEP) + ["img", "iframe"]):
        if el.name in KEEP and el.find_parent(list(KEEP)):
            continue
        if el.name == "img" and el.find_parent(list(KEEP)):
            continue
        if el.name == "p" and not el.get_text(strip=True) and not el.find("img"):
            continue
        clean_attrs(el)
        chunks.append(str(el))
    return "\n".join(chunks)


def rewrite_href(href: str, page_url: str) -> str:
    if not href:
        return href
    if href.startswith("mailto:") or href.startswith("#") or href.startswith("https://www.youtube") or href.startswith("http://youtube") or href.startswith("https://instagram") or href.startswith("http://instagram") or href.startswith("https://www.etsy"):
        return href
    href = href.replace("https://www.elderberrysprout.com", "").replace("https://elderberrysprout.com", "")
    if href.startswith("http"):
        return href
    # relative path from this page
    if "://" not in href:
        base = page_url.rsplit("/", 1)[0]
        while href.startswith("../"):
            href = href[3:]
            base = base.rsplit("/", 1)[0] if "/" in base else ""
        if href.endswith("index.html"):
            href = href[: -len("index.html")]
        if href == "index.html" or href == "":
            path = base or "/"
        else:
            path = f"{base}/{href}" if not href.startswith("/") else href
            if not path.startswith("/"):
                path = "/" + path
        path = re.sub(r"/{2,}", "/", path)
        if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
            path += "/"
        return path
    return href


def text(el: Tag | None) -> str:
    return el.get_text(" ", strip=True) if el else ""


def dump_md(path: Path, meta: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    path.write_text(f"---\n{fm}\n---\n\n{body.strip()}\n", encoding="utf-8")


def first_image(html: str) -> str | None:
    m = re.search(r'src="(/assets/images/[^"]+)"', html)
    return m.group(1) if m else None


def excerpt_from(html: str, n: int = 220) -> str:
    soup = BeautifulSoup(html, "html.parser")
    t = soup.get_text(" ", strip=True)
    t = re.sub(r"\s+", " ", t)
    return (t[: n].rsplit(" ", 1)[0] + "…") if len(t) > n else t


def copy_brand(used: dict[str, str]) -> dict[str, str]:
    mapping = {
        "logo": "9bb10752-9601-4d44-b812-64f889b1bd31_ES+Magical+Living+co.+Logo+Compact+HQ+Alpha+white+Tight+v3.png",
        "logo_long": "a7106968-de5d-46d5-95c9-d8989fce794d_ES+Magical+Living+co.+Logo+long+Alpha+white+Tight.png",
        "logo_footer": "1663636879567-KUVVL69PIHBLIW60768B_ES+Magical+Living+co.+Logo+long+Alpha+white+Tightv2+footer.png",
        "favicon": "39757596-74c1-4778-983a-8be1cc8b0451_favicon.ico",
        "hero": "8fef0c43-d18e-47e5-99ab-9759135e149c_IMG_3404+Candle+Cropped.JPG",
        "banner": "8d90b3bf-4090-496b-b3e7-8fb42014131e_bottom+banner+trial+9+v4.png",
        "marina": "1630705464906-665GGEX6X650O4YVGO8B_Marina+Photo+3278+.JPG",
        "wax": "1631333845437-AAARNXTS7KYXVP7S3TBJ_wide+wax.JPG",
        "grimoire": "1635433897912-U5IYGQTMZP96NLFGW7ZS_Blog+Thumbnail.png",
        "stamp": "1637005052163-D5CWJX9L4XH3HSTO72HH_Stamp.gif",
    }
    out = {}
    for key, src in mapping.items():
        dest = copy_image(src, used)
        if dest:
            # friendly copies
            ext = Path(dest).suffix
            friendly = f"{key}{ext}"
            shutil.copy2(IMG_DST / dest, IMG_DST / friendly)
            out[key] = f"/assets/images/{friendly}"
    return out


def import_posts(sitemap: dict[str, str], used: dict[str, str]) -> int:
    n = 0
    root = OFFLINE / "magic-blog"
    for index in sorted(root.glob("*/index.html")):
        slug = index.parent.name
        if slug in SKIP_DIR_PARTS or index.parent.parent.name in SKIP_DIR_PARTS:
            continue
        if any(p in SKIP_DIR_PARTS for p in index.relative_to(root).parts):
            continue
        s = soup_file(index)
        title_el = s.select_one("h1.entry-title") or s.select_one("h1")
        title = text(title_el)
        if not title or title in {"Magic Blog", "Blog"}:
            continue
        content_el = s.select_one(".blog-item-content")
        if not content_el:
            continue
        page_url = f"/magic-blog/{slug}"
        body = rewrite_content(content_el, used, page_url)
        tags = [text(a) for a in s.select(".blog-item-tag") if text(a)]
        date = sitemap.get(page_url) or sitemap.get(page_url + "/") or "2022-01-01"
        if len(date) == 10:
            dt = date
        else:
            dt = "2022-01-01"
        image = first_image(body)
        meta = {
            "title": title,
            "date": datetime.strptime(dt, "%Y-%m-%d").date(),
            "permalink": f"/magic-blog/{slug}/",
            "tags": tags,
            "author": "Marina Smouse",
            "image": image,
            "excerpt": excerpt_from(body),
        }
        dump_md(POSTS / f"{dt}-{slug}.md", meta, body)
        n += 1
    return n


def import_products(kind: str, dest: Path, url_prefix: str, sitemap: dict[str, str], used: dict[str, str]) -> int:
    n = 0
    root = OFFLINE / kind / "p"
    if not root.is_dir():
        return 0
    for index in sorted(root.glob("*/index.html")):
        slug = index.parent.name
        s = soup_file(index)
        title = text(s.select_one("h1")) or slug.replace("-", " ").title()
        price = text(s.select_one(".product-price-value")) or ""
        price = re.sub(r"\s+", " ", price).strip()
        desc = s.select_one(".product-description")
        page_url = f"{url_prefix}/{slug}"
        body = rewrite_content(desc, used, page_url) if desc else ""
        images = []
        for img in s.select(".product-gallery img, .product-detail img"):
            name = extract_img_name(img.get("src") or img.get("data-src") or "")
            if name:
                dest_name = copy_image(name, used)
                if dest_name:
                    path = f"/assets/images/{dest_name}"
                    if path not in images:
                        images.append(path)
        sold = bool(s.select_one(".product-mark.sold-out")) or "sold out" in text(s.select_one(".product-mark")).lower()
        if kind == "discontinued":
            sold = True
        meta = {
            "title": title,
            "price": price,
            "sold_out": sold,
            "permalink": f"{page_url}/",
            "image": images[0] if images else None,
            "images": images,
            "excerpt": excerpt_from(body, 160),
        }
        dump_md(dest / f"{slug}.md", meta, body)
        n += 1
    return n


def import_videos(sitemap: dict[str, str], used: dict[str, str]) -> int:
    n = 0
    root = OFFLINE / "videos" / "v"
    if not root.is_dir():
        return 0
    for index in sorted(root.glob("*/index.html")):
        slug = index.parent.name
        s = soup_file(index)
        title = text(s.select_one("h1")) or slug.replace("-", " ").title()
        html = str(s)
        m = re.search(r"youtube.com/embed/([A-Za-z0-9_-]{6,})", html)
        youtube = m.group(1) if m else ""
        content_el = s.select_one(".blog-item-content") or s.select_one("[data-sqsp-text-block-content]")
        page_url = f"/videos/v/{slug}"
        body = rewrite_content(content_el, used, page_url) if content_el else ""
        date = sitemap.get(page_url) or "2022-01-01"
        meta = {
            "title": title,
            "date": datetime.strptime(date[:10], "%Y-%m-%d").date() if date else None,
            "permalink": f"{page_url}/",
            "youtube_id": youtube,
            "image": f"https://i.ytimg.com/vi/{youtube}/hqdefault.jpg" if youtube else first_image(body),
            "excerpt": excerpt_from(body, 160),
        }
        dump_md(VIDEOS / f"{slug}.md", meta, body)
        n += 1
    return n


def import_freebies(sitemap: dict[str, str], used: dict[str, str]) -> int:
    n = 0
    root = OFFLINE / "free-digital-downloads"
    FILE_DST.mkdir(parents=True, exist_ok=True)
    for f in FILE_SRC.iterdir():
        if f.is_file():
            shutil.copy2(f, FILE_DST / f.name)
    for index in sorted(root.glob("*/index.html")):
        slug = index.parent.name
        if slug in SKIP_DIR_PARTS:
            continue
        s = soup_file(index)
        title = text(s.select_one("h1")) or slug.replace("-", " ").title()
        if title.startswith("Free Digital"):
            continue
        content_el = s.select_one(".blog-item-content") or s.select_one("article")
        page_url = f"/free-digital-downloads/{slug}"
        body = rewrite_content(content_el, used, page_url) if content_el else ""
        files = []
        for a in s.select("a[href]"):
            href = a.get("href") or ""
            if "assets/files/" in href:
                fname = unquote(href.split("assets/files/", 1)[1].split("?")[0])
                files.append(f"/assets/files/{fname}")
        date = sitemap.get(page_url) or "2022-01-01"
        meta = {
            "title": title,
            "date": datetime.strptime(date[:10], "%Y-%m-%d").date() if date else None,
            "permalink": f"{page_url}/",
            "files": files,
            "image": first_image(body),
            "excerpt": excerpt_from(body, 180),
        }
        dump_md(FREEBIES / f"{slug}.md", meta, body)
        n += 1
    return n


def main() -> None:
    IMG_DST.mkdir(parents=True, exist_ok=True)
    FILE_DST.mkdir(parents=True, exist_ok=True)
    for d in (POSTS, PRODUCTS, DISCONTINUED, VIDEOS, FREEBIES):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    used: dict[str, str] = {}
    brand = copy_brand(used)
    sitemap = parse_sitemap()
    counts = {
        "posts": import_posts(sitemap, used),
        "products": import_products("shop", PRODUCTS, "/shop/p", sitemap, used),
        "discontinued": import_products("discontinued", DISCONTINUED, "/discontinued/p", sitemap, used),
        "videos": import_videos(sitemap, used),
        "freebies": import_freebies(sitemap, used),
        "images": len(list(IMG_DST.iterdir())),
    }
    (ROOT / "content" / "brand.yaml").write_text(yaml.safe_dump(brand), encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
