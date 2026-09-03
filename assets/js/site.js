document.querySelector(".nav-toggle")?.addEventListener("click", () => {
  const nav = document.querySelector(".site-nav");
  const btn = document.querySelector(".nav-toggle");
  const open = nav.classList.toggle("open");
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.setAttribute("aria-label", open ? "Close Menu" : "Open Menu");
});

function hashString(value) {
  let hash = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function mulberry32(seed) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function mixHeading(el) {
  if (el.dataset.cardinalMixed || el.querySelector(".cardinal-alt")) return;
  el.dataset.cardinalMixed = "1";
  const random = mulberry32(hashString(el.textContent));
  let previousAlt = null;

  const mixText = (textNode) => {
    const text = textNode.nodeValue;
    if (!text || !/[^\s]/.test(text)) return;
    const frag = document.createDocumentFragment();
    for (const ch of text) {
      if (/\s/.test(ch)) {
        frag.appendChild(document.createTextNode(ch));
        continue;
      }
      let useAlt = random() < 0.5;
      if (previousAlt !== null && useAlt === previousAlt && random() < 0.7) {
        useAlt = !useAlt;
      }
      previousAlt = useAlt;
      if (useAlt) {
        const span = document.createElement("span");
        span.className = "cardinal-alt";
        span.textContent = ch;
        frag.appendChild(span);
      } else {
        frag.appendChild(document.createTextNode(ch));
      }
    }
    textNode.parentNode.replaceChild(frag, textNode);
  };

  const walk = (node) => {
    [...node.childNodes].forEach((child) => {
      if (child.nodeType === Node.ELEMENT_NODE) walk(child);
      else if (child.nodeType === Node.TEXT_NODE) mixText(child);
    });
  };
  walk(el);
}

document.querySelectorAll("h1, h2, h3, h4").forEach(mixHeading);
