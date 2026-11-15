"""Tests for fetching, parsing, rendering and storage.

Run with:  python -m unittest discover -s tests
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from medium_reader import fetcher, storage
from medium_reader.generator import generate_html
from medium_reader.parser import (
    clean_body, medium_image_id, parse_article, resolve_image_url,
)

LOREM = ("Readers deserve pages that load their images and keep their words intact. " * 12).strip()

FREEDIUM_PAGE = f"""<!doctype html><html><head><title>A Test Article - Freedium</title>
<meta name="description" content="The subtitle"></head><body><main><div><article class="bg-white">
<div><nav class="flex"><a href="/">Home</a></nav></div>
<figure class="image-zoom-figure"><img alt="Post cover image" class="object-cover w-full"
  src="/img/medium/700/1*COVERcoverCOVER.png" data-zoom-src="/img/medium/4000/1*COVERcoverCOVER.png">
  <figcaption class="image-zoom-caption"><!-- --><a href="https://example.com/src">Source<span><svg width="1em"></svg></span></a>, a chart.</figcaption></figure>
<header class="p-6"><p class="mb-2 text-gray-600">November 11, 2026</p>
  <h1 class="mb-4 text-4xl">A Test Article</h1>
  <p class="mb-4 text-xl text-gray-700">The subtitle</p>
  <div class="flex"><div class="flex mr-4"><img class="w-12 h-12 rounded-full" src="/img/medium/700/1*AVATARavatar.png"></div>
  <div><p class="font-semibold">By Jane Writer</p><p class="text-gray-600">7 min read</p></div></div></header>
<section class="px-6"><ul id="toc-list"><li><a href="#intro">Intro</a></li></ul></section>
<div class="p-6"><div class="prose max-w-none"><!--[-->
<h3 id="intro">Intro</h3>
<p class="">{LOREM}</p>
<picture><source media="(max-width: 768px)"><source media="(min-width: 769px)">
<img alt="None" class="prose-image" src="/img/medium/700/1*BODYimageONE.png" data-zoom-src="/img/medium/4000/1*BODYimageONE.png"
 data-caption='&lt;a href="https://news.example/x" rel="nofollow"&gt;News&lt;span&gt;&lt;svg&gt;&lt;/svg&gt;&lt;/span&gt;&lt;/a&gt;, results.'
 width="2000" height="1500" onerror="this.__e=event"></picture>
<h4 id="detail">Detail</h4>
<p>Line one
Line two</p>
<p>{LOREM}</p>
<!--]--></div></div></article></div></main></body></html>"""

MEDIUM_PAGE = f"""<!doctype html><html><head><title>Medium Test | by Sam Author | Medium</title>
<meta property="og:title" content="Medium Test">
<script type="application/ld+json">{{"@type":"NewsArticle","headline":"Medium Test","author":{{"name":"Sam Author"}},
"datePublished":"2021-03-13T18:18:43.264Z","isAccessibleForFree":true,"image":["https://miro.medium.com/v2/resize:fit:1200/1*FIRSTfigure.jpeg"]}}</script>
</head><body><article><div><section><div>
<div><h1 data-testid="storyTitle" class="pw-post-title">Medium Test</h1>
 <img data-testid="authorPhoto" src="https://miro.medium.com/v2/resize:fill:64:64/1*AUTHORpic.jpeg">
 <a data-testid="authorName" href="/@sam">Sam Author</a>
 <span data-testid="storyReadTime">5 min read</span><span data-testid="storyPublishDate">Nov 11, 2017</span>
 <p>Listen</p><p>Share</p></div>
<p class="pw-post-body-paragraph" id="de15">{LOREM}</p>
<figure class="paragraph-image"><div role="button"><span class="speechify-ignore">Press enter or click to view image in full size</span>
 <picture><source srcset="https://miro.medium.com/v2/resize:fit:640/format:webp/1*FIRSTfigure.jpeg 640w, https://miro.medium.com/v2/resize:fit:1400/format:webp/1*FIRSTfigure.jpeg 1400w" type="image/webp">
 <img alt="" class="bh md" width="700" height="394" loading="eager" role="presentation"></picture></div>
 <figcaption class="xx">A figure caption</figcaption></figure>
<h2 class="ov ow" id="196c">Section</h2>
<p class="pw-post-body-paragraph">{LOREM} <a href="/@sam/other-post-abc123" rel="noopener follow">another post</a></p>
</div></section></div></article></body></html>"""


class ImageUrlTests(unittest.TestCase):
    def test_freedium_relative_path_maps_to_medium_cdn(self):
        self.assertEqual(
            resolve_image_url('/img/medium/700/1*jTxIBtlXygY1NoGvMV6bqg.png', 'https://freedium-mirror.cfd/https://x'),
            'https://miro.medium.com/v2/resize:fit:1400/1*jTxIBtlXygY1NoGvMV6bqg.png')

    def test_miro_variants(self):
        for url in ['https://miro.medium.com/v2/resize:fit:640/format:webp/1*abc-_D.jpeg',
                    'https://miro.medium.com/max/700/1*abc-_D.jpeg',
                    'https://cdn-images-1.medium.com/max/800/1*abc-_D.jpeg']:
            self.assertEqual(medium_image_id(url), '1*abc-_D.jpeg', url)

    def test_other_relative_paths_use_base_url(self):
        self.assertEqual(resolve_image_url('/static/x.png', 'https://site.example/a/b'),
                         'https://site.example/static/x.png')

    def test_local_asset_paths_are_kept(self):
        self.assertEqual(resolve_image_url('assets/post/01.png'), 'assets/post/01.png')


class FreediumParsingTests(unittest.TestCase):
    def setUp(self):
        self.article = parse_article(FREEDIUM_PAGE, url='https://medium.com/@jane/a-test-article-0123456789ab',
                                     base_url='https://freedium-mirror.cfd/https://medium.com/@jane/a-test-article-0123456789ab')

    def test_metadata_comes_from_freedium_header(self):
        a = self.article
        self.assertEqual(a.source, 'freedium')
        self.assertEqual(a.title, 'A Test Article')
        self.assertEqual(a.subtitle, 'The subtitle')
        self.assertEqual(a.author, 'Jane Writer')
        self.assertEqual(a.publication_date, 'November 11, 2026')
        self.assertEqual(a.read_time, 7)
        self.assertEqual(a.author_avatar, 'https://miro.medium.com/v2/resize:fit:96/1*AVATARavatar.png')
        self.assertEqual(a.image, 'https://miro.medium.com/v2/resize:fit:1400/1*COVERcoverCOVER.png')
        self.assertIn('href="https://example.com/src"', a.image_caption)
        self.assertNotIn('<svg', a.image_caption)

    def test_body_images_are_absolute_figures_with_captions(self):
        body = self.article.body
        self.assertNotIn('src="/img', body)
        self.assertIn('<figure><img', body)
        self.assertIn('src="https://miro.medium.com/v2/resize:fit:1400/1*BODYimageONE.png"', body)
        self.assertIn('<figcaption><a href="https://news.example/x"', body)
        self.assertNotIn('alt="None"', body)

    def test_framework_markup_is_removed(self):
        body = self.article.body
        for junk in ('class=', 'style=', 'onerror', 'data-', '<svg', '<!--', 'toc-list', 'By Jane Writer', '<picture', '<source'):
            self.assertNotIn(junk, body, junk)

    def test_headings_start_at_h2_and_soft_breaks_kept(self):
        body = self.article.body
        self.assertIn('<h2 id="intro">Intro</h2>', body)
        self.assertIn('<h3 id="detail">Detail</h3>', body)
        self.assertIn('Line one<br/>Line two', body)


class MediumParsingTests(unittest.TestCase):
    def setUp(self):
        self.article = parse_article(MEDIUM_PAGE, url='https://medium.com/@sam/medium-test-0123456789ab')

    def test_metadata(self):
        a = self.article
        self.assertEqual(a.source, 'medium')
        self.assertEqual(a.title, 'Medium Test')
        self.assertEqual(a.author, 'Sam Author')
        self.assertEqual(a.publication_date, 'Nov 11, 2017')  # the visible date, not JSON-LD's
        self.assertEqual(a.read_time, 5)
        self.assertEqual(a.author_avatar, 'https://miro.medium.com/v2/resize:fit:96/1*AUTHORpic.jpeg')

    def test_img_without_src_gets_one_from_picture_sources(self):
        self.assertIn('<img alt="" height="394" src="https://miro.medium.com/v2/resize:fit:1400/1*FIRSTfigure.jpeg"',
                      self.article.body)
        self.assertIn('<figcaption>A figure caption</figcaption>', self.article.body)

    def test_cover_not_repeated_when_it_is_the_first_figure(self):
        self.assertIsNone(self.article.image)

    def test_byline_and_reader_ui_removed(self):
        body = self.article.body
        for junk in ('Listen', 'Share', 'Press enter', 'Sam Author</a>', '5 min read', '<h1'):
            self.assertNotIn(junk, body, junk)

    def test_relative_links_resolved(self):
        self.assertIn('href="https://medium.com/@sam/other-post-abc123"', self.article.body)


class CleanBodyTests(unittest.TestCase):
    def test_idempotent(self):
        once = clean_body(MEDIUM_PAGE, 'https://medium.com/')
        self.assertEqual(clean_body(once), once)

    def test_iframe_gets_single_fallback_link(self):
        once = clean_body('<p>x</p><iframe src="/media/abc" width="680"></iframe>', 'https://medium.com/@a/b')
        twice = clean_body(once)
        self.assertEqual(twice.count('Open embedded content'), 1)
        self.assertIn('src="https://medium.com/media/abc"', twice)


class FetcherTests(unittest.TestCase):
    def _response(self, body: bytes, content_type: str):
        r = requests.Response()
        r._content = body
        r.headers['Content-Type'] = content_type
        r.encoding = requests.utils.get_encoding_from_headers(r.headers)
        return r

    def test_missing_charset_decodes_as_utf8(self):
        r = self._response('Don’t → go'.encode('utf-8'), 'text/html')
        self.assertEqual(r.encoding, 'ISO-8859-1')  # what requests would have used
        self.assertEqual(fetcher.decode_response(r), 'Don’t → go')

    def test_explicit_charset_respected(self):
        r = self._response('café'.encode('latin-1'), 'text/html; charset=ISO-8859-1')
        self.assertEqual(fetcher.decode_response(r), 'café')

    def test_member_only_uses_is_accessible_for_free(self):
        long_free = (f'<script type="application/ld+json">{{"isAccessibleForFree":true}}</script>'
                     f'<p>"isLockedPreviewOnly":false paywall</p><article>{LOREM * 3}</article>')
        self.assertFalse(fetcher._is_member_only_article(long_free))
        paywalled = long_free.replace('true', 'false')
        self.assertTrue(fetcher._is_member_only_article(paywalled))

    def test_falls_through_proxies_and_keeps_preview_last(self):
        preview = fetcher.FetchResult('<article>short</article>', 'https://medium.com/x', 'medium', partial=True)
        with mock.patch.object(fetcher, '_fetch_direct', return_value=preview), \
                mock.patch.object(fetcher, '_fetch_via_proxy', return_value=None) as proxy:
            result = fetcher.fetch_article('https://medium.com/x')
        self.assertEqual(proxy.call_count, len(fetcher.PROXIES))
        self.assertIs(result, preview)

    def test_second_proxy_used_when_first_fails(self):
        good = fetcher.FetchResult('<html/>', 'https://freedium-mirror.cfd/x', 'freedium-mirror.cfd')
        with mock.patch.object(fetcher, '_fetch_direct', return_value=None), \
                mock.patch.object(fetcher, '_fetch_via_proxy', side_effect=[None, good]):
            self.assertIs(fetcher.fetch_article('https://medium.com/x'), good)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {'MEDIUM_READER_DIR': self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_resaving_same_url_overwrites_and_index_lists_it(self):
        url = 'https://medium.com/@jane/a-test-article-0123456789ab'
        article = parse_article(FREEDIUM_PAGE, url=url, base_url='https://freedium-mirror.cfd/' + url)
        first = storage.save_article(generate_html(article), url, article.title)
        second = storage.save_article(generate_html(article), url + '?source=feed', article.title)
        self.assertEqual(first, second)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.html'))), 1)
        index = storage.write_index(Path(self.tmp.name)).read_text()
        self.assertIn('A Test Article', index)
        self.assertIn('Jane Writer', index)

    def test_fix_mojibake(self):
        broken = 'Don’t → stop'.encode('utf-8').decode('latin-1')
        self.assertEqual(storage.fix_mojibake(broken), 'Don’t → stop')
        self.assertEqual(storage.fix_mojibake('café naïve 🐍'), 'café naïve 🐍')

    def test_repair_rerenders_old_page(self):
        old = ('<html><head><title>Old</title></head><body><article><header class="article-header">'
               '<h1 class="article-title">A Test Article</h1></header><div class="article-body">'
               + FREEDIUM_PAGE.encode('utf-8').decode('latin-1') + '</div></article></body></html>')
        path = Path(self.tmp.name) / 'A-Test-Article.html'
        path.write_text(old, encoding='utf-8')
        results = storage.repair_library(Path(self.tmp.name), backup=False)
        self.assertEqual(results['failed'], [])
        page = path.read_text()
        self.assertIn('name="mr:version"', page)
        self.assertIn('Jane Writer', page)
        self.assertNotIn('src="/img', page)


if __name__ == '__main__':
    unittest.main()
