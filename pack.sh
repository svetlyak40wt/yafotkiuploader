#!/bin/sh

VERSION=$(grep '^VERSION' YaFotkiUploader.py | sed "s/VERSION = '\(.*\)'/\1/")

cd ..

tar -jcf YaFotkiUploader-$VERSION.tar.bz2 YaFotkiUploader --exclude .git --exclude '*.swp' --exclude '*.pyc' --exclude '*.jpg' --exclude patches
