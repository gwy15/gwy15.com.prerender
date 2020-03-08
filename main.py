from pathlib import Path
import shutil
import asyncio
import datetime
from time import time
from urllib.parse import quote
from dataclasses import dataclass
from typing import List, Generator

import click
import aiohttp
import pyppeteer
from pyppeteer import launch

PAGE_URL = 'https://gwy15.com'
API_URL = PAGE_URL + '/api'

OUTPUT_PATH = Path('output')
OPTIONS = {
    'headless': True,
    'args': [
        '--user-agent=gwy15-prerenderer'
    ]
}


@dataclass
class PageTask:
    path: str
    name: str
    page_last_modified: int

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
        return OUTPUT_PATH / self.name

    @property
    def lastmod(self):
        assert self.file.exists()
        t = self.file.stat().st_mtime
        return datetime.datetime.fromtimestamp(t)

    def __repr__(self):
        t = datetime.datetime.fromtimestamp(self.page_last_modified)
        return f'<Task {self.name} lastmod={t.strftime("%Y-%m-%d %H:%M:%S")}>'


class TaskFactory:
    @staticmethod
    async def generate_tasks() -> Generator[PageTask, None, None]:
        # /
        yield PageTask(path='/', name='index.html', page_last_modified=time())

        # blogs
        async for task in TaskFactory.generate_blog_tasks():
            yield task

    @staticmethod
    async def generate_blog_tasks() -> Generator[PageTask, None, None]:
        blog_api_url = API_URL + '/blog/post'
        async with aiohttp.request('GET', blog_api_url) as resp:
            posts = await resp.json()
        # /blog/
        yield PageTask(
            path='/blog/', name='blog/index.html',
            page_last_modified=max(post['content']['modified'] for post in posts))
        # /blog/:title
        for post in posts:
            title = post['title']
            yield PageTask(
                path=f'/blog/{title}',
                name=f'blog/{title}',
                page_last_modified=post['content']['modified'])


class Prerenderer:
    async def run(self, force: bool):
        tasks = []
        async for task in TaskFactory.generate_tasks():
            tasks.append(task)

        # prerender
        await self.generate_prerender_pages(tasks, force)

        # generate sitemap
        await self.generate_sitemaps(tasks)
        print('Sitemap generated.')

    async def save(self, content: str, name: str):
        """Write content to file"""
        path = OUTPUT_PATH / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf8') as f:
            f.write(content)

    async def generate_sitemaps(self, tasks: List[PageTask]) -> None:
        XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        {}
        </urlset>"""
        XML_URL_TEMPLATE = """
        <url>
            <loc>{url}</loc>
            <lastmod>{date}</lastmod>
            <changefreq>daily</changefreq>
        </url>"""

        xml_urls = '\n'.join(
            XML_URL_TEMPLATE.format(
                url=task.url,
                date=task.lastmod.strftime('%Y-%m-%d'))
            for task in tasks)
        xml_sitemap = XML_TEMPLATE.format(xml_urls)
        await self.save(xml_sitemap, 'sitemap.xml')

        plaintext = '\n'.join(task.url for task in tasks)
        await self.save(plaintext, 'sitemap.txt')

    async def generate_prerender_pages(self, tasks: List[PageTask], force: bool) -> None:
        browser = None  # lazy ignition

        for task in tasks:
            if not task.need_update(force):
                continue
            if browser is None:
                browser = await launch(OPTIONS)
            page = await browser.newPage()
            print(f'Generating {task}...')
            await page.goto(task.url)
            await asyncio.sleep(0.5)

            content = await page.content()
            await self.save(content, task.name)
            print(f'Page {task.name} generated.')
            # await page.close()
        if browser is not None:
            await asyncio.sleep(1)
            await browser.close()


@click.command()
@click.option('--force', '-F', is_flag=True, help='Force regenerate all pages')
def run(force: bool):
    asyncio.run(Prerenderer().run(force))


if __name__ == "__main__":
    run()
