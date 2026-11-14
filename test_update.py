"""Offline tests; do not require external internet access."""
import sys
from pathlib import Path
import unittest
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update

class TestUpdate(unittest.TestCase):
    def test_rss(self):
        now=update.NOW.strftime('%a, %d %b %Y %H:%M:%S +0000')
        xml=('<?xml version="1.0"?><rss version="2.0"><channel><item>'
              '<title>OpenAI introduces a new AI model</title>'
              '<link>https://example.org/first-story</link>'
              '<pubDate>'+now+'</pubDate>'
              '<description><![CDATA[<p>A publisher-provided description about a new model.</p>]]></description>'
              '</item></channel></rss>')
        item=list(update.feed_items(xml.encode()))[0]
        self.assertEqual(item[0],'OpenAI introduces a new AI model')
        self.assertEqual(item[2],'A publisher-provided description about a new model.')
        self.assertEqual(update.date_parse(item[3]).date(), update.NOW.date())
    def test_atom(self):
        xml=b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
            <title>AI research update</title><link rel="alternate" href="https://example.com/post" />
            <updated>2026-11-14T12:00:00Z</updated><summary>A short research excerpt</summary>
            </entry></feed>'''
        item=list(update.feed_items(xml))[0]
        self.assertEqual(item[1],'https://example.com/post')
        self.assertEqual(item[2],'A short research excerpt')
    def test_sanitizes_markup(self):
        self.assertEqual(update.clean_html('<p>New <b>AI</b> tool</p><script>evil()</script>'),'New AI tool')
        self.assertFalse(update.valid_http_link('javascript:alert(1)'))
    def test_edition_schema_and_audio(self):
        articles=[]
        for n,section in enumerate(('ai','business','vc','startups','ai','vc')):
            articles.append({'id':f'test{n}','title':f'AI news story number {n}', 'source':f'Publisher {n}',
                'url':f'https://example.com/{n}', 'date':(update.NOW-timedelta(hours=n)).isoformat(),
                'section':section,'companies':[], 'topics':['ai'],'tags':[],
                'kind':'Publisher feed','basis':'Publisher-provided feed excerpt.',
                'summary':'An example publisher excerpt about AI funding and products.',
                'simple':'An example publisher excerpt about AI funding and products.',
                'takeaways':[],'why':'Open the source.','vocab':[]})
        edition=update.make_edition(articles,{'OpenAI'}, {})
        self.assertEqual(len(edition['stories']),6)
        self.assertEqual(len(edition['briefing']),6)
        self.assertEqual(len(edition['english']['vocabulary']),5)
        self.assertEqual(len(edition['english']['practice']['questions']),3)
        self.assertTrue(edition['podcast']['lines'])
        self.assertIn('generatedAt',edition)
    def test_low_feed_count_aborts(self):
        with self.assertRaises(RuntimeError):update.make_edition([],set(),{})

if __name__=='__main__':unittest.main()
