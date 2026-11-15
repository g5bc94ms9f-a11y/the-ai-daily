"""Offline editorial checks: no source is fetched from the internet."""
from datetime import timedelta
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import editorial_check
import update

class EditorialTests(unittest.TestCase):
    @staticmethod
    def story(n,title,source='Wired',section='ai'):
        return {'id':f'k{n}', 'title':title,'summary':'A report about AI and business.',
                'simple':'A report about AI and business.',
                'url':f'https://www.wired.com/story/story-{n}/',
                'date':(update.NOW-timedelta(minutes=n)).isoformat(),
                'source':source,'section':section,'kind':'Publisher feed',
                'topics':['ai'],'companies':[], 'tags':[],
                'basis':'RSS publisher excerpt.'}

    def test_reduces_duplicate_founder_news(self):
        items=[self.story(i, t) for i,t in enumerate([
            'Nvidia Jensen Huang ouster has consequences',
            'Jensen Huang and the decline of the visionary showman founder CEO',
            'Jensen Huang and the End of the Founder Fairy Tale',
            'Silicon Valley Is Still Defending Jensen Huang',
            'Jensen Huang is out: Nvidia rivals could benefit',
        ])]
        items += [self.story(100+i,f'OpenAI new model AI feature topic {i}',source=f'Source {i}') for i in range(5)]
        selected=update.pick_stories(items)
        matching=[x for x in selected if update.editorial_cluster(x)=='nvidia-huang-departure']
        self.assertLessEqual(len(matching),2)

    def test_outage_explicitly_not_ai_is_excluded(self):
        from unittest.mock import patch
        from io import BytesIO
        pubdate=update.NOW.strftime('%a, %d %b %Y %H:%M:%S +0000')
        xml=('<rss version="2.0"><channel><item><title>Microsoft 365 outage continues</title>'
             '<description>The company says a bad update—not a cyberattack or AI—caused its servers to crash.</description>'
             '<link>https://www.wired.com/story/outage/</link>'
             f'<pubDate>{pubdate}</pubDate></item></channel></rss>').encode()
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return xml
        with patch.object(update,'urlopen',return_value=Response()):
            result=update.extract(('Wired','https://www.wired.com/rss','Technology Publications','ai',False))
        self.assertEqual(result,[])

    def test_uses_approved_editorial_override(self):
        stories=[self.story(i, 'OpenAI robotics changes') for i in range(4)]
        story_url=stories[0]['url']
        e={'stories':stories,'briefing':[s['id'] for s in stories], 'topAi':[s['id'] for s in stories]}
        status=lambda s:('metadata_checked','Title checked; not fully verified.')
        result=editorial_check.audit(e,{story_url:{'summary':'Corrected, original work continues.',
                                                        'note':'Publisher corrected its earlier wording.'}},checker=status)
        self.assertEqual(result['stories'][0]['reviewStatus'],'editorial_clarification')
        self.assertIn('Corrected',result['stories'][0]['summary'])
        self.assertEqual(result['audit']['editorialClarifications'],1)

    def test_removes_confirmed_broken_links(self):
        stories=[self.story(i,'AI headline') for i in range(5)]
        result=editorial_check.audit({'stories':stories,'briefing':[s['id'] for s in stories], 'topAi':[]}, {},
            checker=lambda s:('unavailable','HTTP 404') if s['id']=='k0' else ('feed_only','RSS only'))
        self.assertEqual(len(result['stories']),4)
        self.assertEqual(result['audit']['quarantinedOrUnavailableStories'],1)
        self.assertNotIn('k0',result['briefing'])

    def test_correction_is_quarantined_without_override(self):
        stories=[self.story(i,'OpenAI headline') for i in range(5)]
        result=editorial_check.audit({'stories':stories,'briefing':[], 'topAi':[]},{},
            checker=lambda s:('corrected','Publisher correction notice') if s['id']=='k0' else ('feed_only','RSS only'))
        self.assertNotIn('k0',[story['id'] for story in result['stories']])
        self.assertEqual(result['audit']['quarantinedOrUnavailableStories'],1)

    def test_trusted_domain_and_title_similarity(self):
        self.assertTrue(editorial_check.trusted_host('https://www.wired.com/story/example'))
        self.assertFalse(editorial_check.trusted_host('https://wired.com.attacker.example/story'))
        self.assertFalse(editorial_check.trusted_host('http://www.wired.com'))
        self.assertTrue(editorial_check.similar_title('New AI model from Google announced',
                                                     'Google announces new AI model update'))
        self.assertFalse(editorial_check.similar_title('NVIDIA earnings rise after chip sales',
                                                      'Ancient Roman culture archaeology'))

if __name__=='__main__':unittest.main()
