#!/usr/bin/env python3
"""The AI Daily RSS edition builder. No API key or external Python packages.

Only uses publisher-provided RSS/Atom titles/excerpts and direct links; does not
claim to have read the full story. Never fabricates a claim to fill missing data.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone, time
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'data' / 'edition.js'
NOW = datetime.now(timezone.utc)
EARLIEST = NOW - timedelta(days=7)
MAX_STORIES = 35
MIN_STORIES = 4

# These are publisher feeds, not site-scraping endpoints. Some can block bots,
# change URLs, or have publication delays; errors are reported, not concealed.
FEEDS = [
    ('OpenAI', 'https://openai.com/news/rss.xml', 'AI Companies', 'ai', True),
    ('Google DeepMind', 'https://deepmind.google/blog/rss.xml', 'AI Companies', 'ai', True),
    ('NVIDIA', 'https://blogs.nvidia.com/feed/', 'AI Companies', 'ai', True),
    ('The Verge', 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 'Technology Publications', 'ai', False),
    ('Ars Technica', 'https://arstechnica.com/ai/feed/', 'Technology Publications', 'ai', False),
    ('Wired', 'https://www.wired.com/feed/tag/ai/latest/rss', 'Technology Publications', 'ai', False),
    ('MIT Technology Review', 'https://www.technologyreview.com/topic/artificial-intelligence/feed', 'Technology Publications', 'ai', False),
    ('MIT News', 'https://news.mit.edu/rss/topic/artificial-intelligence2', 'Technology Publications', 'ai', True),
    ('The Decoder', 'https://the-decoder.com/feed/', 'Technology Publications', 'ai', False),
    ('Crunchbase News', 'https://news.crunchbase.com/feed/', 'Startups & Venture Capital', 'vc', False),
    ('Artificial Lawyer', 'https://www.artificiallawyer.com/feed/', 'AI & Business', 'business', False),
    ('LawSites', 'https://www.lawsitesblog.com/feed', 'AI & Business', 'business', False),
    ('Google News · Anthropic', 'https://news.google.com/rss/search?q=Anthropic+Claude+when%3A7d&hl=en-US&gl=US&ceid=US%3Aen', 'AI Companies', 'ai', False),
]
DIRECT = [
    ('Anthropic', 'https://www.anthropic.com/news', 'AI Companies', 'Company news page; Google News stories are collected separately'),
    ('Google Gemini', 'https://blog.google/products/gemini/', 'AI Companies', 'Company news page'),
    ('Microsoft', 'https://blogs.microsoft.com/', 'AI Companies', 'Company news page'),
    ('Meta AI', 'https://ai.meta.com/blog/', 'AI Companies', 'Company news page'),
    ('Hugging Face', 'https://huggingface.co/blog', 'AI Companies', 'Company blog'),
    ('TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/', 'Technology Publications', 'Direct link; RSS terms restrict modifying feed content'),
    ('VentureBeat AI', 'https://venturebeat.com/category/ai/', 'Technology Publications', 'Direct link; legacy AI feed may not update'),
    ('Y Combinator', 'https://www.ycombinator.com', 'Startups & Entrepreneurship', 'Startup accelerator and company news'),
    ('Startup Stealth', 'https://startupstealth.com', 'Startups & Entrepreneurship', 'Original magazine source; direct link only'),
    ('Startup Ideas', 'https://startup-ideas.com', 'Startups & Entrepreneurship', 'Original magazine source; direct link only'),
    ('Early Startup Days', 'https://www.earlystartupdays.com/subscribe', 'Startups & Entrepreneurship', 'Original magazine source; direct link only'),
    ('Andreessen Horowitz (a16z)', 'https://a16z.com', 'Venture Capital', 'Investor articles and podcasts'),
    ('ApexRound', 'https://apexround.com', 'Venture Capital', 'Original magazine source; direct link only'),
    ('Simply You Grow', 'https://algofirst.co/marketing', 'Founders & Business', 'Original magazine source; direct link only'),
    ('Business Bulls', 'https://www.instagram.com/businessbulls.in/', 'Founders & Business', 'Original Instagram source; direct link only'),
    ('Beyond Startup', 'https://www.instagram.com/beyondstartup.s/', 'Founders & Business', 'Original Instagram source; direct link only'),
    ('Harvey', 'https://www.harvey.ai/newsroom', 'AI & Business', 'Legal AI company news'),
    ('FinTech Futures', 'https://www.fintechfutures.com/', 'AI & Business', 'Finance and technology reporting'),
]

BUSINESS = re.compile(r'\b(law|legal|lawyer|finance|financial|fund|bank|business|enterprise|corporate|workplace|productivity|workforce|office|accounting|compliance|contract|insurance|fintech|investment|investor|earnings|revenue|market|economy)\b', re.I)
VENTURE = re.compile(r'\b(raise[ds]?|raised|raising|fundrais\w*|round|valuation|valued|investor|investment|invested|venture|vc|ipo|startup|founder|seed|series [a-f]|acquisition|acquire[ds]?|merger|capital|backed|funding|unicorn)\b', re.I)
STARTUP = re.compile(r'\b(startup|founder|launch|launched|accelerator|entrepreneur|yc|y combinator|small business)\b', re.I)
AI = re.compile(r'\b(ai|artificial intelligence|llm|language model|agentic|ai agent|chatgpt|openai|anthropic|claude|gemini|deepmind|nvidia|machine learning|generative|neural|inference|copilot|gpt[- ]?\d|robotics|transformer|hugging face)\b', re.I)
COMPANIES = {'OpenAI':r'\bopenai\b|\bchatgpt\b|\bgpt\b', 'Anthropic':r'\banthropic\b|\bclaude\b', 'Google Gemini':r'\bgemini\b', 'DeepMind':r'\bdeepmind\b', 'Microsoft':r'\bmicrosoft\b|\bcopilot\b', 'Meta':r'\bmeta\b|\bllama\b', 'NVIDIA':r'\bnvidia\b', 'Apple':r'\bapple\b|\bsiri\b'}
GLOSSARY = [
    ('funding round','noun','FUN-ding round','an investment stage in which a startup raises capital','The startup announced a new funding round.'),
    ('valuation','noun','val-yoo-AY-shun','an estimate of what a company is worth','The company announced a new valuation.'),
    ('IPO','noun','eye-pee-OH','an initial public offering, when a company first sells stock to the public','Investors are discussing a potential IPO.'),
    ('inference','noun','IN-fer-ens','the process of using a trained AI model to produce an answer','AI inference requires computing power.'),
    ('agent','noun','AY-jent','a software system that can carry out steps toward a goal','An AI agent can help organize a workflow.'),
    ('model','noun','MAH-dul','an AI system trained to recognize patterns and produce outputs','The company introduced a new AI model.'),
    ('chip','noun','chip','a small electronic processor used in computers','AI systems run on powerful chips.'),
    ('startup','noun','START-up','a young company trying to build a scalable business','The startup is testing a new product.'),
    ('launch','verb','lawnch','to introduce a new product or service','The company plans to launch a product.'),
    ('acquisition','noun','ak-wih-ZIH-shun','the purchase of one company by another','The acquisition would expand the business.'),
    ('revenue','noun','REV-uh-noo','money a company earns from sales','Revenue is different from profit.'),
    ('benchmark','noun','BENCH-mark','a test used to compare performance','The benchmark measures the model’s speed.'),
    ('open source','adjective','OH-pen sors','software whose source code is available under an open license','Developers contribute to open-source projects.'),
    ('enterprise','noun','EN-ter-pryze','a company, especially a large organization','Enterprise customers often have security requirements.'),
    ('regulation','noun','reg-yuh-LAY-shun','an official rule governing an activity','A new regulation may affect the industry.'),
]

class StripHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script','style'): self.skip += 1
        if tag.lower() in ('p', 'div', 'br', 'li'): self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag.lower() in ('script','style') and self.skip: self.skip -= 1
        if tag.lower() in ('p','div','li'): self.parts.append(' ')
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def clean_html(value):
    p = StripHTML()
    p.feed(unescape(value or ''))
    return re.sub(r'\s+', ' ', unescape(''.join(p.parts))).strip()

def child_text(node, *names):
    for name in names:
        c = node.find(name)
        if c is not None and c.text and c.text.strip(): return c.text.strip()
    return ''

def date_parse(raw):
    if not raw: return None
    try:
        parsed = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try: parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        except ValueError: return None
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def valid_http_link(link):
    try:
        p = urlparse(link)
        return p.scheme == 'https' and bool(p.netloc) and not p.username and not p.password
    except ValueError:
        return False

def feed_items(xml_bytes):
    """Parse RSS 2.0, RSS namespaced, and Atom without installed packages."""
    if len(xml_bytes) > 3_000_000: raise ValueError('Feed is too large')
    root = ET.fromstring(xml_bytes)
    nodes = root.findall('.//item')
    if nodes:
        for node in nodes:
            title = clean_html(child_text(node,'title'))
            link = child_text(node,'link')
            if not link:
                for c in node:
                    if c.tag.split('}')[-1]=='link' and c.text: link=c.text.strip(); break
            desc = child_text(node,'description','{http://purl.org/rss/1.0/modules/content/}encoded','{http://purl.org/dc/elements/1.1/}description')
            if not desc:
                for c in node:
                    if c.tag.split('}')[-1] in ('summary','description','encoded'): desc=c.text or ''; break
            date = child_text(node,'pubDate','{http://purl.org/dc/elements/1.1/}date')
            yield title, link, clean_html(desc), date
        return
    ns = '{http://www.w3.org/2005/Atom}'
    for node in root.findall('.//'+ns+'entry'):
        title = clean_html(child_text(node,ns+'title'))
        link = ''
        for a in node.findall(ns+'link'):
            if a.get('rel','alternate')=='alternate' and a.get('href'):
                link=a.get('href'); break
        desc = child_text(node,ns+'summary',ns+'content')
        date = child_text(node,ns+'published',ns+'updated')
        yield title,link,clean_html(desc),date

def teaser(description, title):
    """Brief, publisher-attributed feed excerpts, not full-article summaries."""
    value = re.sub(r'\s*(?:Read more|Continue reading)(?:\s+.*)?$', '', description, flags=re.I).strip()
    value = re.sub(r'\s*\[\.{3}\]$', '', value).strip()
    # Keep the publisher excerpt short; do not generate unsourced details.
    if len(value)>240:
        part=value[:241]
        cut=max(part.rfind('. '),part.rfind('! '),part.rfind('? '))
        value=part[:cut+1] if cut>=95 else part[:237].rsplit(' ',1)[0]+'…'
    if not value or value.casefold()==title.casefold():
        return 'Read the source article for the full reporting and context.'
    return value

def section_for(title, description, preferred):
    # Recognize categories conservatively. AI, business, startup and VC overlap.
    text=(title+' '+description[:140]).lower()
    if BUSINESS.search(title) and not VENTURE.search(title): return 'business'
    if VENTURE.search(title): return 'vc' if re.search(r'\b(invest|fund|round|rais|ipo|valuation|acqui|merger|capital|venture)\w*',title,re.I) else 'startups'
    if STARTUP.search(title) and not AI.search(title): return 'startups'
    if preferred=='vc' and (STARTUP.search(text) or VENTURE.search(text)): return 'vc'
    return 'ai'

def extract(feed):
    name,url,group,preferred,official=feed
    req=Request(url, headers={'User-Agent':'TheAIDailyReader/1.0 (+news digest; contact via linked publisher sites)', 'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5'})
    with urlopen(req,timeout=18) as resp:
        body=resp.read(3_000_001)
    story=[]
    for title,link,desc,raw_date in feed_items(body):
        d=date_parse(raw_date)
        if not title or not valid_http_link(link) or not d: continue
        if d < EARLIEST or d > NOW + timedelta(hours=6): continue
        if not (official or AI.search(title+' '+desc) or VENTURE.search(title) or (preferred=='business' and BUSINESS.search(title))):
            continue
        # Avoid unrelated NVIDIA consumer hardware/gaming content.
        if name=='NVIDIA' and not AI.search(title+' '+desc[:160]): continue
        if name=='Crunchbase News' and not (AI.search(title+' '+desc) or VENTURE.search(title)): continue
        summary=teaser(desc,title)
        section=section_for(title,desc,preferred)
        if preferred=='business' and BUSINESS.search(title+' '+desc[:100]): section='business'
        company=[n for n,p in COMPANIES.items() if re.search(p,title+' '+desc[:160],re.I)]
        if name in ('OpenAI','Google DeepMind','NVIDIA') and not company: company=[name]
        topics=['ai']
        if section in ('vc','startups'): topics += [section, 'founders']
        if section=='business': topics+=['law-finance']
        if 'NVIDIA' in company: topics+=['nvidia-infra']
        if 'Anthropic' in company or 'OpenAI' in company: topics+=['openai-anthropic']
        if 'Google Gemini' in company or 'DeepMind' in company: topics+=['gemini']
        if 'Apple' in company: topics+=['apple']
        kind='Official announcement' if official else ('News aggregation' if name.startswith('Google News') else 'Publisher feed')
        sid=hashlib.sha256(link.encode('utf-8')).hexdigest()[:16]
        basis=('Google News RSS search headline and excerpt. This is an aggregation link; verify the original publisher before relying on the claim.'
               if name.startswith('Google News') else
               'Publisher-provided RSS/Atom title and short excerpt. We have not verified the full article.')
        story.append({
          'id': sid, 'title':title[:230], 'source':name, 'url':link, 'date':d.isoformat().replace('+00:00','Z'),
          'section': section, 'companies':company, 'topics':list(dict.fromkeys(topics)), 'tags':[],
          'kind':kind, 'basis':basis,
          'summary':summary, 'simple':'This story was published by '+name+'. Its headline is: '+title+'. Follow the original link for the full article.', 'takeaways':[], 'why':'',
          'vocab':[]
        })
    return story[:12]

def pick_stories(entries):
    # Deduplicate title despite multiple publishers covering the same headline.
    seen=set(); unique=[]; per_source={}
    for item in sorted(entries,key=lambda s:s['date'],reverse=True):
        fingerprint = re.sub(r'[^a-z0-9]+',' ',item['title'].lower()).strip()
        if fingerprint in seen or per_source.get(item['source'],0)>=7: continue
        seen.add(fingerprint); unique.append(item)
        per_source[item['source']]=per_source.get(item['source'],0)+1
    # Balance business, startups, VC and core AI stories.
    groups={k:[] for k in ('ai','business','vc','startups')}
    for s in unique: groups[s['section']].append(s)
    chosen=[]; used=set()
    for section in ('ai','business','vc','startups'):
        for s in groups[section][:5 if section=='ai' else 4]:
            if s['id'] not in used: chosen.append(s); used.add(s['id'])
    for s in unique:
        if len(chosen)>=MAX_STORIES: break
        if s['id'] not in used: chosen.append(s); used.add(s['id'])
    return sorted(chosen,key=lambda s:s['date'],reverse=True)[:MAX_STORIES]

def make_english(stories):
    corpus=' '.join(s['title']+' '+s['summary'] for s in stories).lower()
    vocabulary=[]
    for term,pos,say,meaning,example in GLOSSARY:
        regex=r'(?<!\w)'+re.escape(term)+r'(?!\w)'
        for s in stories:
            if re.search(regex,s['title']+' '+s['summary'],re.I):
                vocabulary.append({'term':term,'pos':pos,'say':say,'meaning':meaning,'example':example,'from':s['id']})
                break
        if len(vocabulary)>=5:break
    if len(vocabulary)<4:
        for term,pos,say,meaning,example in GLOSSARY:
            if term not in {v['term'] for v in vocabulary}:
                vocabulary.append({'term':term,'pos':pos,'say':say,'meaning':meaning,'example':example,'from':stories[0]['id']})
            if len(vocabulary)>=5:break
    focus=stories[0]
    sections=['Artificial intelligence','Startups and entrepreneurship','Venture capital','AI in business']
    sec_names={'ai':sections[0],'startups':sections[1],'vc':sections[2],'business':sections[3]}
    correct_section=sec_names[focus['section']]
    other_sections=[s for s in sections if s!=correct_section][:2]
    possible_sources=list(dict.fromkeys(x['source'] for x in stories if x['source']!=focus['source']))
    # Use source names as choices to ensure answer is grounded in article metadata.
    src_options=[focus['source']]+possible_sources[:2]
    if len(src_options)<3: src_options += ['Another publication']*(3-len(src_options))
    # Questions ask about metadata, not the unseen full article.
    questions=[
        {'q':'Which publication is credited with today’s featured story?', 'options':src_options, 'answer':0, 'explain':'The source is '+focus['source']+'. You can open its original article.'},
        {'q':'Which main topic does the featured story belong to?', 'options':[other_sections[0],correct_section,other_sections[1]], 'answer':1, 'explain':'The magazine categorizes this story as '+correct_section.lower()+'.'},
        {'q':'Where can you check the full details beyond this short excerpt?', 'options':['The original publisher link','An AI-generated guess','The magazine’s navigation menu'], 'answer':0, 'explain':'Use the link to the original publisher. The feed excerpt alone may omit important context.'}
    ]
    return {
      'vocabulary':vocabulary,
      'read':{'storyId':focus['id'],'expressions':[
          {'phrase':'according to','note':'A useful way to attribute information: According to the report, …'},
          {'phrase':'roll out','note':'In technology reporting, to roll out means to introduce a product or feature.'},
          {'phrase':'raise capital','note':'To obtain money from investors to finance a business.'}]},
      'practice':{'storyId':focus['id'],'questions':questions,
          'writing':'Write 3–4 sentences about the featured story. Begin with “According to the report…” and clearly distinguish reported facts from your opinion.',
          'speaking':'In 30 seconds, explain the featured headline in American English. Mention the source and use “according to.”',
          'expressions':[
              {'phrase':'according to','meaning':'used to name the source of a claim','example':'According to the report, the company released a new feature.'},
              {'phrase':'roll out','meaning':'to introduce something gradually or publicly','example':'The team plans to roll out an update next month.'},
              {'phrase':'keep an eye on','meaning':'to watch something for new developments','example':'Investors are keeping an eye on AI spending.'}]}
    }

def make_podcast(brief):
    lines=[
      [0,'Welcome to The AI Daily, your morning overview of artificial intelligence, startups, investing and business.'],
      [1,'This is an automated audio reading of publishers’ RSS headlines and short excerpts. It does not replace the original reporting.'],
    ]
    for i,s in enumerate(brief[:7],1):
        lines.append([0,f'Story {i}. From {s["source"]}: {s["title"]}.'])
        if s['summary'] != 'Read the source article for the full reporting and context.':
            lines.append([1,s['summary']])
        else:
            lines.append([1,'Visit the original article for more information.'])
    lines += [[0,'That is your daily briefing. Open any story to read the original publisher.'],[1,'Thanks for listening. Keep learning.']]
    return {'title':'The AI Daily Audio Briefing','blurb':'Listen to publisher headlines and short excerpts in American English.','hosts':['Maya','Ben'],'lines':lines}

def sources_for(ok,error):
    """Keep every original source link chosen for The AI Daily preview."""
    catalog = json.loads((ROOT/'data'/'source_catalog.json').read_text(encoding='utf-8'))
    by_group={g['group']:[] for g in catalog}
    used=set()
    for group in catalog:
        for item in group['items']:
            name=item['name']
            if name in used: continue
            used.add(name)
            status='Checked via publisher feed in the latest update' if name in ok else 'Direct site link; not automatically checked'
            by_group[group['group']].append({'name':name,'url':item['url'], 'mode':'edition' if name in ok else 'link', 'note':status})
    for name,url,group,_,_ in FEEDS:
        if name in used: continue
        used.add(name)
        note='Included in this update' if name in ok else ('Feed failed this update' if name in error else 'No eligible recent stories in this update')
        if name.startswith('Google News'):note+='; aggregator, not the original publisher'
        by_group.setdefault(group,[]).append({'name':name,'url':url,'mode':'edition' if name in ok else 'link','note':note})
    for name,url,group,note in DIRECT:
        if name in used: continue
        used.add(name)
        by_group.setdefault(group,[]).append({'name':name,'url':url,'mode':'link','note':note})
    return [{'group':group,'items':items} for group,items in by_group.items()]

def make_edition(entries,ok,error):
    stories=pick_stories(entries)
    if len(stories)<MIN_STORIES:
        raise RuntimeError(f'Only {len(stories)} eligible articles found across {len(ok)} feeds; refusing to replace the last good edition.')
    # Select briefing with some topic diversity, then fill with newest.
    briefing=[]
    for section in ('ai','vc','business','startups'):
        match=next((s for s in stories if s['section']==section and s['id'] not in briefing),None)
        if match: briefing.append(match['id'])
    for s in stories:
        if len(briefing)>=7: break
        if s['id'] not in briefing: briefing.append(s['id'])
    ai_top=[s['id'] for s in stories if s['section']=='ai'][:5]
    sorted_brief=[next(s for s in stories if s['id']==i) for i in briefing]
    notes=[
        'Automatically collected from RSS/Atom feeds shown under My Sources. Most titles/excerpts come from publishers; Google News results are labeled as aggregator feeds. The AI Daily does not independently verify or summarize full articles.',
        'The edition is refreshed daily; articles may be several days old, especially on weekends. Check publication dates and original links.',
        'Audio and English exercises are generated from available headlines/excerpts. This edition does not use a paid AI summarization service.'
    ]
    if error:notes.append(f'{len(error)} feed(s) were unavailable for this update: '+', '.join(sorted(error))+'.')
    scheduled = datetime.combine(NOW.date(), time(9, 17), tzinfo=timezone.utc)
    if scheduled <= NOW: scheduled += timedelta(days=1)
    return {'label':'Live RSS edition','nextUpdate':scheduled.isoformat().replace('+00:00','Z'),
      'notes':notes,'briefing':briefing,'topAi':ai_top,'stories':stories,
      'english':make_english(stories),'sources':sources_for(ok,error),
      'podcast':make_podcast(sorted_brief), 'generatedAt':NOW.isoformat().replace('+00:00','Z'),
      'builtAt':NOW.isoformat().replace('+00:00','Z')}

def main():
    stories=[];ok=set();error={}
    with ThreadPoolExecutor(max_workers=5) as pool:
        future={pool.submit(extract,feed):feed for feed in FEEDS}
        for f in as_completed(future):
            name=future[f][0]
            try:
                result=f.result()
                if result:
                    stories.extend(result);ok.add(name)
                    print(f'OK {name}: {len(result)} recent items',flush=True)
                else:
                    print(f'EMPTY {name}: no eligible items',flush=True)
            except Exception as e:
                error[name]=type(e).__name__
                print(f'ERROR {name}: {type(e).__name__}: {e}',file=sys.stderr,flush=True)
    edition=make_edition(stories,ok,error)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text('window.AI_EDIT = '+json.dumps(edition,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'Published {len(edition["stories"])} stories from {len(ok)} feeds to {OUTPUT}',flush=True)

if __name__=='__main__': main()
