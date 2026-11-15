#!/usr/bin/env python3
"""Conservative editorial metadata audit. No AI-generated claim verification.

Caution: reading an RSS excerpt or loading a publisher page is NOT fact checking.
Unreachable pages remain labeled as feed-only. HTTP 404/410 and explicitly
revised/corrected stories are handled before a podcast is generated.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json
import re

ROOT=Path(__file__).resolve().parents[1]
EDITION=ROOT/'data'/'edition.js'
OVERRIDES=ROOT/'data'/'editorial_overrides.json'
HOSTS=('openai.com','anthropic.com','blog.google','deepmind.google',
       'nvidia.com','theverge.com','wired.com','arstechnica.com',
       'technologyreview.com','news.mit.edu','the-decoder.com',
       'techcrunch.com','news.crunchbase.com','artificiallawyer.com',
       'lawsitesblog.com','ycombinator.com','huggingface.co')
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; TheAIDailyEditorialCheck/1.0)',
         'Accept':'text/html,application/xhtml+xml;q=0.9'}

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title=''
        self.description=''
    def handle_starttag(self,tag,attrs):
        if tag!='meta':return
        a=dict(attrs)
        key=(a.get('property') or a.get('name') or '').lower()
        if key in ('og:title','twitter:title'):self.title=self.title or a.get('content','')
        if key in ('og:description','description'):self.description=self.description or a.get('content','')


def trusted_host(url):
    try:
        p=urlparse(url)
        host=(p.hostname or '').lower()
        return p.scheme=='https' and any(host==h or host.endswith('.'+h) for h in HOSTS)
    except ValueError:return False


def similar_title(feed_title,page_title):
    def terms(s):
        stop={'the','of','and','how','why','in','with','for','from','says','on','at','a','an','to','is','are','new','ai','report'}
        return {w for w in re.findall(r'[a-z0-9]+',s.lower()) if len(w)>=3 and w not in stop}
    f,p=terms(feed_title),terms(page_title)
    if len(f)<3 or len(p)<3:return True  # Insufficient evidence.
    return len(f&p)/min(len(f),len(p))>=0.48


def fetch_status(article):
    if article.get('kind')=='News aggregation':return ('aggregator','Google News is an aggregator, not the original article.')
    url=article.get('url','')
    if not trusted_host(url):return ('feed_only','Publisher page is outside the allowed metadata-check domains.')
    try:
        req=Request(url,headers=HEADERS)
        with urlopen(req,timeout=6) as response:
            final_url=response.geturl()
            if not trusted_host(final_url):return ('feed_only','Publisher redirected outside allowed domains.')
            ct=response.headers.get('Content-Type','').lower()
            if 'text/html' not in ct and 'application/xhtml+xml' not in ct:
                return ('feed_only','Publisher page did not return HTML metadata.')
            raw=response.read(240000).decode('utf-8',errors='replace')
        meta=Metadata();meta.feed(raw)
        # Only classify corrections when explicitly labeled in article markup.
        correction=bool(re.search(r'<(?:p|div|strong|b)[^>]*>\s*(?:<strong[^>]*>\s*)?(?:Correction|Editor.s note|Updated?\s+(?:on|at))\s*[:—–-]',raw,re.I))
        if correction:return ('corrected','The publisher page contains a correction/update notice; consult the current article.')
        if meta.title and not similar_title(article['title'],meta.title):
            return ('changed','Publisher-page headline differs materially from the feed headline; consult the updated article.')
        return ('metadata_checked','Publisher-page title was compared with RSS metadata; full article claims were not fact-checked.')
    except HTTPError as e:
        if e.code in (404,410):return ('unavailable',f'Original publisher URL returned HTTP {e.code}.')
        return ('feed_only',f'Publisher page could not be checked (HTTP {e.code}).')
    except (URLError,TimeoutError,ConnectionError,OSError,ValueError):
        return ('feed_only','Publisher page could not be accessed; RSS headline and excerpt only.')
    except Exception:
        return ('feed_only','Publisher metadata check did not complete; RSS headline and excerpt only.')


def audit(edition,override_data,checker=fetch_status):
    original=edition.get('stories',[])
    # Feed archives may have a correction not yet represented in page metadata.
    # Reviewed editorial overrides are exact-URL matches, and do not invent an
    # automatic verification of the rest of the article.
    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses=list(pool.map(checker,original))
    checked=[];removed=0
    for story,(status,note) in zip(original,statuses):
        override=override_data.get(story.get('url',''))
        if status=='unavailable' or (status in ('changed','corrected') and not override):
            # Hold uncertain stories out of both the magazine and podcast until
            # the publisher's current text or a reviewed correction is available.
            removed+=1
            continue
        if override:
            story['summary']=override['summary']
            story['simple']='This report has an editorial clarification. '+override['summary']
            story['editorialNote']=override.get('note','Editorial clarification applied.')
            story['reviewStatus']='editorial_clarification'
            story['basis']='RSS publisher title; editorial clarification added with reference to the linked source. '+story['editorialNote']
        else:
            story['reviewStatus']=status
            story['editorialNote']=note
            if status in ('corrected','changed'):
                story['summary']='The publisher has updated or corrected this article. Read the original report for the current details.'
                story['simple']=story['summary']
            story['basis']='RSS publisher title/excerpt. '+note
        checked.append(story)
    if len(checked)<4:
        raise RuntimeError('Editorial audit left fewer than four usable stories; last published edition will be preserved.')
    ids={s['id'] for s in checked}
    edition['stories']=checked
    edition['briefing']=[i for i in edition.get('briefing',[]) if i in ids]
    for story in checked:
        if len(edition['briefing'])>=7:break
        if story['id'] not in edition['briefing']:edition['briefing'].append(story['id'])
    edition['topAi']=[s['id'] for s in checked if s['section']=='ai'][:5]
    edition['audit']={'checkedAt':datetime.now(timezone.utc).isoformat(),
                      'method':'RSS attribution + accessible publisher page metadata and editorial override rules, not full independent fact checking',
                      'pageMetadataChecked':sum(s['reviewStatus']=='metadata_checked' for s in checked),
                      'feedOnly':sum(s['reviewStatus']=='feed_only' for s in checked),
                      'publisherChanges':sum(s['reviewStatus'] in ('corrected','changed') for s in checked),
                      'editorialClarifications':sum(s['reviewStatus']=='editorial_clarification' for s in checked),
                      'quarantinedOrUnavailableStories':removed}
    edition.setdefault('notes',[]).append(
        'Editorial checks compare available publisher-page metadata, quarantine changed or corrected articles pending editorial clarification, exclude confirmed broken URLs, and apply reviewed clarifications. ' 
        'This does not constitute independent fact verification of every article.')
    return edition


def main():
    raw=EDITION.read_text(encoding='utf-8').strip()
    prefix='window.AI_EDIT = '
    if not raw.startswith(prefix):raise ValueError('Unexpected edition format')
    edition=json.loads(raw[len(prefix):].removesuffix(';'))
    overrides=json.loads(OVERRIDES.read_text(encoding='utf-8'))
    result=audit(edition,overrides)
    EDITION.write_text(prefix+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print('Editorial audit:',result['audit'],flush=True)

if __name__=='__main__':main()
