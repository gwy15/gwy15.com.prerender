docker.receipt: chrome-linux.zip Dockerfile main.py requirements.txt Makefile
	docker build . -t prerenderer
	echo `date` > $@
chrome-linux.zip:
	wget https://storage.googleapis.com/chromium-browser-snapshots/Linux_x64/575458/chrome-linux.zip
