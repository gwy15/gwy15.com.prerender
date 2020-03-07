#! /bin/bash
cd "${0%/*}"
mkdir -p output
chmod -R 777 output
docker run -it --rm --init --cap-add=SYS_ADMIN \
    -v /tmp/prerender/output:/home/pptruser/prerender:rw \
    prerenderer
chmod -R 775        output/*
chown -R 1000:10000 output/*
