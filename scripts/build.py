#!/usr/bin/env python3
"""Build the Elderberry Sprout static site into _site/."""

from __future__ import annotations

import hashlib
import random
import shutil
from datetime import date, datetime
from pathlib import Path

import markdown
import yaml
from bs4 import BeautifulSoup, NavigableString
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
SITE = ROOT / "_site"
ASSETS = ROOT / "assets"

SITE_INFO = {
    "title": "Elderberry Sprout",
    "description": "Magical tools for magical folks. Love infused beeswax candles for your spiritual practice.",
    "url": "https://www.elderberrysprout.com",
    "email": "elderberrysprout@protonmail.com",
    "youtube": "https://www.youtube.com/c/elderberrysprout",
    "instagram": "https://www.instagram.com/elderberrysprout",
    "etsy": "https://www.etsy.com/shop/elderberrysprout",
    "logo": "/assets/images/logo_footer.png",
    "logo_long": "/assets/images/logo_long.png",
    "favicon": "/assets/images/favicon.ico",
    "hero": "/assets/images/hero.jpg",
}

HOME_FAVORITES = [
    "kundalini-twist-beeswax-candle",
    "small-taper",
    "large-taper",
    "birthday-candle-bundle",
    "beeswax-number-candles",
    "chime-candle",
]


def tag_slug(tag: str) -> str:
    return str(tag).strip().rstrip("]").strip().lower().replace(" ", "-")


def pretty_date(value) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%b %d, %Y").replace(" 0", " ")
    return str(value) if value else ""


def collect_blog_nav(posts: list[dict]) -> tuple[list[dict], list[dict]]:
    tag_counts: dict[str, int] = {}
    year_counts: dict[int, int] = {}
    for post in posts:
        for tag in post.get("tags") or []:
            name = str(tag).strip().rstrip("]").strip()
            if name:
                tag_counts[name] = tag_counts.get(name, 0) + 1
        d = post.get("date")
        if isinstance(d, datetime):
            d = d.date()
        if isinstance(d, date):
            year_counts[d.year] = year_counts.get(d.year, 0) + 1
    # Keep the browse bar to recurring topics. One-off tags still appear on posts.
    min_count = 2
    generic = {"magic"}
    browse_tags = [
        {"name": name, "slug": tag_slug(name), "count": count}
        for name, count in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        if count >= min_count and name.lower() not in generic
    ]
    browse_years = [
        {"year": year, "count": count}
        for year, count in sorted(year_counts.items(), reverse=True)
    ]
    return browse_tags, browse_years


def env() -> Environment:
    jinja = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    jinja.filters["tag_slug"] = tag_slug
    return jinja


def parse_item(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {"title": path.stem, "permalink": f"/{path.stem}/", "content": raw, "body": raw}
    end = raw.find("\n---", 3)
    if end < 0:
        return {"title": path.stem, "permalink": f"/{path.stem}/", "content": raw, "body": raw}
    fm = raw[4:end]
    body = raw[end + 4 :].lstrip("\n")
    meta = yaml.safe_load(fm) or {}
    body = body.strip()
    if path.suffix == ".md" and body and not body.lstrip().startswith("<"):
        html = markdown.markdown(body, extensions=["extra", "sane_lists"])
    else:
        html = body
    meta["content"] = html
    meta["body"] = body
    meta.setdefault("slug", path.stem)
    if isinstance(meta.get("date"), datetime):
        meta["date"] = meta["date"].date()
    if isinstance(meta.get("tags"), list):
        meta["tags"] = [str(t).strip().rstrip("]").strip() for t in meta["tags"] if str(t).strip()]
    meta["date_label"] = pretty_date(meta.get("date"))
    return meta


def load_dir(folder: Path) -> list[dict]:
    if not folder.is_dir():
        return []
    items = [parse_item(p) for p in sorted(folder.glob("*.md"))]
    items.sort(key=lambda i: str(i.get("date") or ""), reverse=True)
    return items


def pick_by_slug(items: list[dict], slugs: list[str]) -> list[dict]:
    by_slug = {item.get("slug"): item for item in items}
    return [by_slug[slug] for slug in slugs if slug in by_slug]


def heading_rng(text: str) -> random.Random:
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def mix_heading_text(node: NavigableString, soup: BeautifulSoup, rng: random.Random, prev: bool | None) -> bool | None:
    text = str(node)
    if not any(not ch.isspace() for ch in text):
        return prev
    pieces: list = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            pieces.append("".join(buf))
            buf.clear()

    for ch in text:
        if ch.isspace():
            buf.append(ch)
            continue
        flush()
        use_alt = rng.random() < 0.5
        if prev is not None and use_alt == prev and rng.random() < 0.7:
            use_alt = not use_alt
        prev = use_alt
        if use_alt:
            span = soup.new_tag("span", attrs={"class": "cardinal-alt"})
            span.string = ch
            pieces.append(span)
        else:
            buf.append(ch)
    flush()
    node.replace_with(*pieces)
    return prev


def mix_headings(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if tag.find(class_="cardinal-alt"):
            continue
        original = " ".join(tag.get_text().split())
        rng = heading_rng(original)
        prev: bool | None = None

        def walk(parent) -> None:
            nonlocal prev
            for child in list(parent.children):
                if isinstance(child, NavigableString):
                    prev = mix_heading_text(child, soup, rng, prev)
                elif getattr(child, "name", None):
                    walk(child)

        walk(tag)
        tag["data-cardinal-mixed"] = "1"
        if original:
            tag["aria-label"] = original
        for link in tag.find_all("a"):
            label = " ".join(link.get_text().split())
            if label:
                link["aria-label"] = label
    return str(soup)


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mix_headings(html), encoding="utf-8")


def out_path(permalink: str) -> Path:
    p = permalink.strip("/")
    if not p:
        return SITE / "index.html"
    return SITE / p / "index.html"


def wrap(jinja: Environment, inner: str, **ctx) -> str:
    ctx.setdefault("site", SITE_INFO)
    ctx["content"] = inner
    return jinja.get_template("base.html").render(**ctx)


def render_page(jinja: Environment, template: str, **ctx) -> str:
    ctx.setdefault("site", SITE_INFO)
    inner = jinja.get_template(template).render(**ctx)
    return wrap(jinja, inner, **ctx)


def copy_assets() -> None:
    dest = SITE / "assets"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ASSETS, dest)
    cname = ROOT / "CNAME"
    if cname.is_file() and cname.read_text(encoding="utf-8").strip():
        shutil.copy2(cname, SITE / "CNAME")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    jinja = env()
    posts = load_dir(CONTENT / "posts")
    products = load_dir(CONTENT / "products")
    discontinued = load_dir(CONTENT / "discontinued")
    videos = load_dir(CONTENT / "videos")
    freebies = load_dir(CONTENT / "freebies")
    pages = load_dir(CONTENT / "pages")

    copy_assets()

    write(
        SITE / "index.html",
        render_page(
            jinja,
            "home.html",
            title=SITE_INFO["title"],
            description=SITE_INFO["description"],
            posts=posts[:4],
            products=pick_by_slug(products, HOME_FAVORITES),
            image=SITE_INFO["hero"],
        ),
    )

    browse_tags, browse_years = collect_blog_nav(posts)
    blog_nav = {"browse_tags": browse_tags, "browse_years": browse_years, "kind": "post"}
    write(
        out_path("/magic-blog/"),
        render_page(
            jinja,
            "list.html",
            title="Magic Blog",
            heading="Magic Blog",
            items=posts,
            **blog_nav,
        ),
    )
    write(
        out_path("/magic/"),
        render_page(
            jinja,
            "list.html",
            title="Blog",
            heading="Magic Blog",
            items=posts,
            **blog_nav,
        ),
    )
    write(out_path("/shop/"), render_page(jinja, "list.html", title="Shop", heading="Shop", items=products, kind="product", note="Checkout is not available on this site. Email to inquire about a piece, or visit the Etsy shop if it is still listed."))
    write(out_path("/discontinued/"), render_page(jinja, "list.html", title="Previous Collections", heading="Previous Collections", items=discontinued, kind="product"))
    write(out_path("/videos/"), render_page(jinja, "list.html", title="Videos", heading="Videos", items=videos, kind="video"))
    write(out_path("/free-digital-downloads/"), render_page(jinja, "list.html", title="Freebies", heading="Free Digital Grimoire Pages", items=freebies, kind="freebie"))

    for post in posts:
        write(out_path(post["permalink"]), render_page(jinja, "post.html", **post, og_type="article"))
    for item in products + discontinued:
        write(out_path(item["permalink"]), render_page(jinja, "product.html", **item))
    for item in videos:
        write(out_path(item["permalink"]), render_page(jinja, "video.html", **item))
    for item in freebies:
        write(out_path(item["permalink"]), render_page(jinja, "freebie.html", **item))
    for page in pages:
        write(out_path(page["permalink"]), render_page(jinja, "page.html", **page))

    tags: dict[str, list] = {}
    years: dict[int, list] = {}
    for post in posts:
        for tag in post.get("tags") or []:
            tags.setdefault(tag, []).append(post)
        d = post.get("date")
        if isinstance(d, datetime):
            d = d.date()
        if isinstance(d, date):
            years.setdefault(d.year, []).append(post)
    for tag, items in tags.items():
        slug = tag_slug(tag)
        write(
            out_path(f"/magic-blog/tag/{slug}/"),
            render_page(
                jinja,
                "list.html",
                title=f"{tag} — Magic Blog",
                heading="Magic Blog",
                items=items,
                active_tag=tag,
                **blog_nav,
            ),
        )
    for year, items in years.items():
        write(
            out_path(f"/magic-blog/{year}/"),
            render_page(
                jinja,
                "list.html",
                title=f"{year} — Magic Blog",
                heading="Magic Blog",
                items=items,
                active_year=year,
                **blog_nav,
            ),
        )

    write(
        SITE / "404.html",
        wrap(
            jinja,
            '<div class="prose"><h1>Page not found</h1><p>This page is not on the new site. Try the <a href="/">home page</a> or <a href="/magic-blog/">Magic Blog</a>.</p></div>',
            title="Not found",
        ),
    )
    print(f"built {SITE} posts={len(posts)} products={len(products)} videos={len(videos)} freebies={len(freebies)}")


if __name__ == "__main__":
    main()
