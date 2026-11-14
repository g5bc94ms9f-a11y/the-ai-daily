// Cloudflare Pages Function: GET /api/news
// It reads public RSS feeds server-side (avoiding browser CORS limitations).
// No private keys or user accounts. No Instagram scraping. Uses source publication dates.
const SOURCES = [
  { name: 'OpenAI', url: 'https://openai.com/news/rss.xml', group: 'Official', priority: 1 },
  { name: 'Anthropic', url: 'https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml', group: 'Official', priority: 1, independent: true },
  { name: 'Google Gemini', url: 'https://blog.google/products-and-platforms/products/gemini/rss/', group: 'Official', priority: 1 },
  { name: 'Google DeepMind', url: 'https://deepmind.google/blog/rss.xml', group: 'Official', priority: 1 },
  { name: 'Google AI', url: 'https://blog.google/technology/ai/rss/', group: 'Official', priority: 1 },
  { name: 'TechCrunch AI', url: 'https://techcrunch.com/category/artificial-intelligence/feed/', group: 'Industry', priority: 2 },
  { name: 'Hugging Face', url: 'https://huggingface.co/blog/feed.xml', group: 'Industry', priority: 2 },
];

function decode(v) {
  return String(v || '')
    .replace(/^<!\[CDATA\[|\]\]>$/g, '')
    .replace(/&#(x[\da-f]+|\d+);/gi, (_, n) => {
      const num = n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : parseInt(n, 10);
      return num > 0 && num <= 0x10ffff ? String.fromCodePoint(num) : '';
    })
    .replace(/&(?:amp|lt|gt|quot|apos|nbsp|hellip|rsquo|lsquo|ldquo|rdquo);/g, (x) => ({
      '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'", '&nbsp;': ' ',
      '&hellip;': '…', '&rsquo;': '’', '&lsquo;': '‘', '&ldquo;': '“', '&rdquo;': '”'
    })[x] || x);
}
function content(xml, tag) {
  const r = new RegExp('<' + tag.replace(/:/g,'\\:') + '(?:\\s[^>]*)?>([\\s\\S]*?)<\\/' + tag.replace(/:/g,'\\:') + '\\s*>', 'i');
  return (xml.match(r) || [,''])[1];
}
function textOnly(v) {
  return decode(v).replace(/<[^>]*>/g,' ').replace(/\s+/g, ' ').trim();
}
function safeURL(v) {
  try { const u = new URL(decode(v)); return /^https?:$/.test(u.protocol) ? u.href : ''; } catch { return ''; }
}
function parseRSS(xml, src) {
  const rows = [];
  const items = xml.match(/<item\b[^>]*>[\s\S]*?<\/item\s*>/gi) || [];
  // Normalize standard RSS 2.0 items; Atom-only sources are intentionally not used.
  for (const item of items.slice(0, 22)) {
    const title = textOnly(content(item, 'title'));
    const link = safeURL(textOnly(content(item, 'link')));
    const pubDate = textOnly(content(item, 'pubDate') || content(item, 'dc:date'));
    const description = textOnly(content(item, 'description') || content(item, 'content:encoded')).slice(0, 330);
    if (!title || !link || !pubDate || !Number.isFinite(Date.parse(pubDate))) continue;
    const enclosure = (item.match(/<(?:media:content|media:thumbnail|enclosure)\b[^>]*\burl=["']([^"']+)["']/i) || [,''])[1];
    const innerImage = (content(item,'description').match(/<img\b[^>]*\bsrc=["']([^"']+)["']/i) || [,''])[1];
    rows.push({
      id: link, title: title.slice(0, 240), link, pubDate, description,
      image: safeURL(enclosure || innerImage),
      source: src.name, group: src.group, priority: src.priority, independent: !!src.independent
    });
  }
  return rows;
}
async function loadFeed(src) {
  const c = new AbortController();
  const timer = setTimeout(() => c.abort(), 10500);
  try {
    const res = await fetch(src.url, {
      headers: { Accept: 'application/rss+xml, application/xml, text/xml', 'User-Agent': 'TheAIEditPersonalReader/2.0' },
      signal: c.signal
    });
    if (!res.ok) throw Error('HTTP '+res.status);
    const xml = await res.text();
    if (xml.length > 1_500_000) throw Error('Feed too large');
    return parseRSS(xml, src);
  } finally { clearTimeout(timer); }
}
export async function onRequestGet() {
  const results = await Promise.allSettled(SOURCES.map(loadFeed));
  const articles = results.flatMap(r => r.status === 'fulfilled' ? r.value : []);
  const n = results.filter(r => r.status === 'fulfilled' && r.value.length).length;
  const byUrl = new Map();
  for (const article of articles) {
    const key = article.link.replace(/\/$/, '').toLowerCase();
    if (!byUrl.has(key)) byUrl.set(key, article);
  }
  const json = {
    articles: [...byUrl.values()].sort((a,b) => Date.parse(b.pubDate)-Date.parse(a.pubDate)).slice(0,140),
    sourcesResponding: n,
    sourcesTotal: SOURCES.length,
    fetchedAt: new Date().toISOString(),
    disclaimer: 'Article summaries and dates come from original RSS publishers. Anthropic articles are indexed by an independent feed.'
  };
  return new Response(JSON.stringify(json), {
    status: json.articles.length ? 200 : 503,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=600, s-maxage=1200, stale-while-revalidate=3600',
      'X-Content-Type-Options': 'nosniff',
      'Access-Control-Allow-Origin': '*'
    }
  });
}
