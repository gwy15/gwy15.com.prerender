from pathlib import Path
import asyncio
import datetime
import time
from typing import List
from copy import copy
from datetime import timezone as tz
from urllib.parse import quote
from dataclasses import dataclass
from typing import List, Generator, Union

import click
import aiohttp
from pyppeteer import launch, launcher

PAGE_URL = 'https://gwy15.com'
API_URL = PAGE_URL + '/api'

OUTPUT_PATH = Path('output')
def options(locale):
    return {
        'headless': True,
        'args': [
            '--user-agent=gwy15-prerenderer',
            f'--lang={locale}'
        ]
    }
XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{}
</urlset>
"""
XML_URL_TEMPLATE = """
    <url>
        <loc>{url}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>hourly</changefreq>
    </url>
"""


@dataclass
class PageTask:
    path: str
    name: str
    page_last_modified: int
    locale: str

    @staticmethod
    def from_url(path: str, locale):
        assert path.startswith('/')
        return PageTask(
            path=path,
            name=path.lstrip('/'),
            page_last_modified=int(time.time()),
            locale=locale
        )

    def need_update(self, force: bool) -> bool:
        if force:
            return True

        if not self.file.exists():
            return True

        return self.page_last_modified > self.file.stat().st_mtime

    @property
    def url(self):
        return PAGE_URL + quote(self.path)

    @property
    def file(self) -> Path:
        return OUTPUT_PATH / self.locale / (self.name + '.html')

    @property
    def lastmod(self):
        assert self.file.exists()
        t = self.file.stat().st_mtime
        return datetime.datetime.fromtimestamp(
            t, tz.utc).replace(microsecond=0)

    def __repr__(self):
        t = datetime.datetime.fromtimestamp(
            self.page_last_modified, tz.utc).replace(microsecond=0)
        return f'<Task {self.path} lastmod={t.isoformat()}>'


class TaskFactory:
    @staticmethod
    async def generate_tasks(locale) -> Generator[PageTask, None, None]:
        yield PageTask.from_url('/privacy-policy', locale)
        yield PageTask.from_url('/terms-of-service', locale)
        # blogs
        async for task in TaskFactory.generate_blog_tasks(locale):
            yield task
        # genshin
        # yield PageTask.from_url('/genshin/map')
        yield PageTask.from_url('/genshin/sow', locale)

    @staticmethod
    async def generate_blog_tasks(locale) -> Generator[PageTask, None, None]:
        blog_api_url = API_URL + '/blog/posts'
        async with aiohttp.request('GET', blog_api_url) as resp:
            posts = await resp.json()
        latest_change = max(post['content']['modified'] for post in posts)
        # /
        yield PageTask(
            path='/', name='index',
            page_last_modified=latest_change,
            locale=locale)

        # /blog
        yield PageTask(
            path='/blog', name='blog',
            page_last_modified=latest_change,
            locale=locale)

        # /blog/:title
        for post in posts:
            title = post['title'].replace(' ', '-')
            yield PageTask(
                path=f'/blog/{title}',
                name=f'blog/{title}',
                page_last_modified=post['content']['modified'],
                locale=locale)


class Prerenderer:
    async def run(self, locales: List[str], force: bool):
        for locale in locales:
            await self.run_with_locale(locale, force)
        # wait for graceful shutdown on Windows, related to
        # https://github.com/aio-libs/aiohttp/issues/4324
        await asyncio.sleep(1)

    async def run_with_locale(self, locale: str, force: bool):
        tasks = []
        async for task in TaskFactory().generate_tasks(locale):
            tasks.append(task)

        # prerender pages
        print('generating prerender pages')
        browser = await self.get_browser(locale)
        try:
            await self.generate_prerender_pages(browser, tasks, force)
        finally:
            await asyncio.sleep(1)
            print("killing browser")
            await browser.close()
            await asyncio.sleep(1)

        # generate sitemap
        await self.generate_sitemaps(tasks, locale)
        print('Sitemap generated.')

    async def get_browser(self, locale: str):
        print(f'starting browser with locale {locale}')
        browser = await launch(options(locale))
        return browser

    async def save(self, content: str, path: Path):
        """Write content to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf8') as f:
            f.write(content)

    async def generate_sitemaps(self, tasks: List[PageTask], locale: str) -> None:
        print('generating sitemaps')
        xml_urls = ''.join(
            XML_URL_TEMPLATE.format(
                url=task.url,
                lastmod=task.lastmod.isoformat())
            for task in tasks)
        xml_sitemap = XML_TEMPLATE.format(xml_urls)
        await self.save(xml_sitemap, OUTPUT_PATH / locale / 'sitemap.xml')

        plaintext = '\n'.join(task.url for task in tasks)
        await self.save(plaintext, OUTPUT_PATH / locale / 'sitemap.txt')

    async def generate_prerender_pages(
            self, browser: launcher.Browser, tasks: List[PageTask],
            force: bool) -> None:
        for task in tasks:
            if not task.need_update(force):
                continue
            page = await browser.newPage()
            print(f'Generating {task}...')
            await page.goto(task.url)
            await asyncio.sleep(0.5)

            content = await page.content()
            await self.save(content, task.file)
            print(f'Page {task.name} generated.')
            # await page.close()


@click.command()
@click.option('--force', '-F', is_flag=True, help='Force regenerate all pages')
def run(force: bool):
    asyncio.run(Prerenderer().run(
        [
            'en-US', 'zh-CN'
        ], force))


if __name__ == "__main__":
    run()
