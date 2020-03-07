#! /bin/bash
set -e
cd "${0%/*}"
# clear output directory
rm    -rf output && mkdir -p output
# change permissions
chown -R 999:999    output && chmod -R 775  output
docker run -it --rm --init --cap-add=SYS_ADMIN \
    -v `pwd`/output:/home/pptruser/output \
    prerenderer
# hand over permission to main user
chown -R 1000:1000  output && chmod -R 775  output
