from pathlib import Path
import shutil
import asyncio
import datetime
from urllib.parse import quote

import aiohttp
import pyppeteer
from pyppeteer import launch

PAGE_URL = 'https://gwy15.com'
API_URL = PAGE_URL + '/api'
ROUTES = [
    ['/', 'index'],
    ['/blog/', 'blog/index'],
    # ...
]
OUTPUT_PATH = Path('prerender')
USER_AGENT = 'gwy15-prerenderer'
OPTIONS = {
    'headless': True,
    'args': [
        f'--user-agent={USER_AGENT}'
    ]
}


async def extend_routes(routes):
    url = API_URL + '/blog/post'
    async with aiohttp.request('GET', url) as resp:
        data = await resp.json()
    for item in data:
        title = item['title']
        ROUTES.append([
            f'/blog/{title}', f'blog/{title}'
        ])


async def generate_site_map(routes):
    template = """<?xml version="1.0" encoding="UTF-8" ?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        {}
    </urlset>"""
    url_template = """
    <url>
        <loc>{url}</loc>
        <lastmod>{date}</lastmod>
        <changefreq>daily</changefreq>
    </url>"""

    def route_to_info(route):
        return {
            'url': PAGE_URL + quote(route[0]),
            'date': datetime.date.today().strftime('%Y-%m-%d')
        }

    urls = '\n'.join(
        url_template.format(**route_to_info(route))
        for route in routes
    )
    result = template.format(urls)
    await save(result, OUTPUT_PATH / 'sitemap.xml')

    plaintext = '\n'.join(
        PAGE_URL + quote(route[0])
        for route in routes
    )
    await save(plaintext, OUTPUT_PATH / 'sitemap.txt')
    print('sitemap generated.')


async def save(content: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf8') as f:
        f.write(content)


async def generate_prerender_pages():
    browser = await launch(OPTIONS)

    for route, name in ROUTES:
        page = await browser.newPage()
        await page.setUserAgent(USER_AGENT)
        print(f'Generating {name}...')
        await page.goto(PAGE_URL + route)
        await asyncio.sleep(0.5)
        content = await page.content()
        await save(content, OUTPUT_PATH / (name + '.html'))
        await save(content, OUTPUT_PATH / name)
        print(f'Page {name} generated.')
        # await page.close()
    await asyncio.sleep(1)
    await browser.close()


async def main():
    shutil.rmtree(str(OUTPUT_PATH), ignore_errors=True)
    OUTPUT_PATH.mkdir(exist_ok=True)
    #
    await extend_routes(ROUTES)

    # generate sitemap.txt and xml
    await generate_site_map(ROUTES)

    #
    await generate_prerender_pages()


asyncio.run(main())
