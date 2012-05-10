#!/usr/bin/env python

from distutils.core import setup

setup(name = 'yafotki',
      version = '0.3.0',
      description = 'Client library for Yandex.Fotki.',
      author = 'Alexander Artemenko',
      author_email = 'art@yandex-team.ru',
      url = 'http://fotki.yandex.ru/',
      packages = ['yafotki',],
      scripts = ['yaploader',],
)
