#!/bin/sh

VERSION=$(grep '^VERSION' YaFotki/__init__.py | sed "s/VERSION = '\(.*\)'/\1/")

[ -e .git ] && git-log --pretty=format:"%ai  %an%n%n  * %s%n" > ChangeLog

cd ..

tar -jcf YaFotkiUploader-$VERSION.tar.bz2 YaFotkiUploader \
        --exclude .git \
        --exclude '*.swp' \
        --exclude '*.pyc' \
        --exclude '*.jpg' \
        --exclude patches \
        --exclude images
