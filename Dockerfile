FROM kubeless/unzip AS chrome-downloader
# url: https://storage.googleapis.com/chromium-browser-snapshots/Linux_x64/575458/chrome-linux.zip
COPY chrome-linux.zip /tmp/
RUN unzip -q /tmp/chrome-linux.zip -d /tmp/chrome/

# === phase 2: build ===
FROM python:3.8-slim
# install dependencies for chrome
# dependencies from https://github.com/puppeteer/puppeteer/blob/master/docs/troubleshooting.md
RUN sed -i s/deb.debian.org/mirrors.aliyun.com/ /etc/apt/sources.list \
    && sed -i s/security.debian.org/mirrors.aliyun.com/ /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --fix-missing \
        gconf-service libasound2 libatk1.0-0 libatk-bridge2.0-0 libc6 libcairo2 \
        libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 \
        libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 \
        libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
        libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 \
        libxss1 libxtst6 ca-certificates fonts-liberation libappindicator1 libnss3 \
        lsb-release xdg-utils wget \
    && apt-get clean && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
# copy chrome
COPY --from=chrome-downloader /tmp/chrome/ \
    /home/pptruser/.local/share/pyppeteer/local-chromium/575458/
# setup sandbox and add user
RUN groupadd -r pptruser \
    && useradd -r -g pptruser -G audio,video pptruser \
    && mkdir /home/pptruser/output \
    && chown -R pptruser:pptruser /home/pptruser \
    && chmod -R 775 /home/pptruser
# install py dependencies
WORKDIR /home/pptruser
COPY requirements.txt requirements.txt
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt

USER pptruser
COPY main.py main.py

CMD [ "python", "main.py" ]
# CMD ["bash"]
