# Elderberry Sprout

Website for [elderberrysprout.com](https://www.elderberrysprout.com), rebuilt from the Squarespace archive so it can live on GitHub Pages.

## Write a blog post

1. Add a file under `content/posts/` named like `2026-09-02-my-post-title.md`
2. Start it with:

```markdown
---
title: My Post Title
date: 2026-09-02
permalink: /magic-blog/my-post-title/
tags: [magic]
author: Marina Smouse
---

Write here. Blank lines make new paragraphs.

![A candle](/assets/images/your-photo.jpg)
```

3. Put photos in `assets/images/`.
4. Push to GitHub (or ask Cursor to). The site rebuilds in a minute or two.

## Local preview

```bash
./.venv/bin/python scripts/build.py
./.venv/bin/python -m http.server -d _site 8000
```

Then open http://127.0.0.1:8000
