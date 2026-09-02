#!/usr/bin/env python3
"""Build the Elderberry Sprout static site into _site/."""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path

import markdown
import yaml
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
    "logo": "/assets/images/logo.png",
    "logo_long": "/assets/images/logo_long.png",
    "logo_footer": "/assets/images/logo_footer.png",
    "favicon": "/assets/images/favicon.ico",
    "hero": "/assets/images/hero.jpg",
}


def env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


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
    return meta


def load_dir(folder: Path) -> list[dict]:
    if not folder.is_dir():
        return []
    items = [parse_item(p) for p in sorted(folder.glob("*.md"))]
    items.sort(key=lambda i: str(i.get("date") or ""), reverse=True)
    return items


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


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
            products=products[:6],
            image=SITE_INFO["hero"],
        ),
    )

    write(
        out_path("/magic-blog/"),
        render_page(jinja, "list.html", title="Magic Blog", heading="Magic Blog", items=posts, kind="post"),
    )
    write(out_path("/magic/"), render_page(jinja, "list.html", title="Blog", heading="Magic Blog", items=posts, kind="post"))
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
    for post in posts:
        for tag in post.get("tags") or []:
            tags.setdefault(tag, []).append(post)
    for tag, items in tags.items():
        slug = tag.lower().replace(" ", "-")
        write(
            out_path(f"/magic-blog/tag/{slug}/"),
            render_page(jinja, "list.html", title=tag, heading=tag, items=items, kind="post"),
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
