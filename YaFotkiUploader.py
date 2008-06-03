#!/usr/bin/env python
# -*- coding: utf-8 -*-

####
# 05/2008 Alexander Atemenko <svetlyak.40wt@gmail.com>
#
# Special thanks to:
# Grigory Bakunov <bobuk@justos.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import MultipartPostHandler, urllib2, cookielib
import os, sys, re, md5, random
import urllib
import logging
import time
import getpass

from BeautifulSoup import BeautifulSoup
from pdb import set_trace
from xml.dom import minidom
from StringIO import StringIO

logging.basicConfig(level=logging.WARNING)

VERSION = '0.2.2'

try:
    from pyexiv2 import Image as ImageExif
except:
    logging.getLogger('start').warning('can\'t find python-pyexiv2 library, exif extraction will be disabled.')
    ImageExif = None

ALBUMS_URL= 'http://fotki.yandex.ru/users/%s/albums/'
UPLOAD_URL = 'http://up.fotki.yandex.ru/upload'

CONFIG_PATH = '~/.fotki.conf'
COOKIES_CACHE = '~/.fotki.cookies'

_conf = None
def config(conffile=CONFIG_PATH):
    '''Simple config loader with singleton instance'''
    global _conf
    if _conf:
        return _conf
    res = {}

    conffile = os.path.expanduser(conffile)
    if os.path.isfile(conffile):
        for line in (x.strip() for x in open(conffile).readlines()):
            if '=' not in line:
                [key, value] = [line, True]
            else:
                [key, value] = [x.strip() for x in line.split('=')]
            res[key] = value
    _conf = res
    return _conf

def get_albums(username, cookies):
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies), MultipartPostHandler.MultipartPostHandler)

    fake_file = StringIO('<?xml version="1.0" encoding="utf-8"?><client-upload name="get-albums"/>')

    params = {
        'query-type' : 'photo-command',
        'command-xml' : fake_file
    }

    try:
        data = opener.open(UPLOAD_URL, params).read()
        xml = minidom.parseString(data)
        albums = []
        for album in xml.getElementsByTagName('album'):
            id = album.attributes['id'].value
            title = album.getElementsByTagName('title')[0].firstChild.nodeValue
            albums.append( (id, title) )
        return albums

    except urllib2.URLError, err:
        print err
        pass
    return []


def print_albums(albums):
    for album in albums:
        print '%s\t%s' % album

def post_img(cookies, img, album, username):
    logger = logging.getLogger('post_img')
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies), MultipartPostHandler.MultipartPostHandler)

    filename = os.path.split(img)[-1]
    tags = ''
    title = filename
    description = ''

    if ImageExif:
        exif = ImageExif(img)
        exif.readMetadata()
        try: tags = ','.join(exif['Iptc.Application2.Keywords'])
        except KeyError: pass
        try: title = exif['Iptc.Application2.ObjectName']
        except KeyError: pass
        try: description = exif['Exif.Image.ImageDescription'] or exif['Iptc.Application2.Caption']
        except KeyError: pass

    source = open(img, 'rb')
    source.seek(0, 2)
    file_size = source.tell()
    piece_size = 64000

    sid = str(int(time.time()))
    source.seek(0)
    hash = md5.new(source.read()).hexdigest()

    logger.debug('md5hash: %s, sid: %s, file-size: %s, piece-size: %s' % (hash, sid, file_size, piece_size))

    logger.debug('photo-start')
    # START
    fake_file = StringIO('<?xml version="1.0" encoding="utf-8"?><client-upload md5="%(md5)s" cookie="%(md5)s%(sid)s"><filename>%(filename)s</filename><title>%(title)s</title><description>%(description)s</description><albumId>%(album)s</albumId><copyright>0</copyright><tags>%(tags)s</tags></client-upload>' % {
        'md5': hash,
        'sid': sid,
        'filename': filename,
        'title': title,
        'album': album,
        'tags': tags,
        'description': description,
    })

    params = {
        'query-type': 'photo-start',
        'file-size': str(file_size),
        'piece-size': str(piece_size),
        'checksum': hash,
        'client-xml': fake_file,
    }

    try:
        data = opener.open(UPLOAD_URL, params).read()
        logger.debug(data)
        response = minidom.parseString(data).firstChild
        a = response.attributes
        if a['status'].value == 'error':
            if a['exception'].value == '3':
                logger.error('Album with id %s does not exist.' % album)
            else:
                logger.error('Error during upload, with code %s' % a['exception'].value)
            sys.exit(1)
        upload_cookie = str(a['cookie'].value)
    except urllib2.URLError, err:
        logger.error(err)
        logger.error(err.read())
        return err

    source.seek(0)
    offset = 0
    while 1:
        data = source.read(piece_size)
        if not data:
            break

        logger.debug('photo-piece')

        piece = StringIO(data)

        params = {
            'query-type': 'photo-piece',
            'cookie': upload_cookie,
            'offset': str(offset),
            'fragment': piece,
        }

        try:
            data = opener.open(UPLOAD_URL, params).read()
            logger.debug(data)
        except urllib2.URLError, err:
            logger.error(err)
            logger.error(err.read())
            return err

        offset += source.tell()

    logger.debug('photo-checksum')

    params = {
        'query-type': 'photo-checksum',
        'cookie': upload_cookie,
        'size': str(file_size),
    }

    try:
        data = opener.open(UPLOAD_URL, params).read()
        logger.debug(data)
    except urllib2.URLError, err:
        logger.error(err)
        logger.error(err.read())

        logger.debug('check-upload')
        fake_file = StringIO('<?xml version="1.0" encoding="utf-8"?><client-upload name="check-upload" cookie="%(md5)s%(sid)s" login="%(login)s"></client-upload>' % {
            'md5': hash,
            'sid': sid,
            'login': username,
        })

        params = {
            'query-type': 'photo-command',
            'command-xml': fake_file,
        }
        try:
            data = opener.open(UPLOAD_URL, params).read()
            logger.debug(data)
            response = minidom.parseString(data).firstChild
            if response.nodeName != 'images':
                logger.error('error upload check: %s' % data)
                sys.exit(1)
        except urllib2.URLError, err:
            logger.error(err)
            logger.error(err.read())
            return err

    logger.debug('photo-finish')

    params = {
        'query-type': 'photo-finish',
        'cookie': upload_cookie,
    }

    try:
        data = opener.open(UPLOAD_URL, params).read()
        logger.debug(data)

        response = minidom.parseString(data).firstChild
        if response.attributes['status'].value == 'error':
            logger.error('error during upload, with code %s' % response.attributes['exception'].value)
    except urllib2.URLError, err:
        logger.error(err)
        logger.error(err.read())


def post(cookie, img, album, username):
    if os.path.exists(img):
        print 'Uploading %s to album %s' % (img, album)
        post_img(cookie, img, album, username)
    else:
        print "Can't find image %s on the disk" % img


def createAuthOpener(user, passwd):
    cj = cookielib.LWPCookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    ccache = os.path.expanduser(COOKIES_CACHE)
    if 'use_cookies_cache' in config():
        if os.path.isfile(ccache):
            cj.load(ccache)
            cj.clear_expired_cookies()
            for ck in cj:
                if ck.name == 'yandex_login' and ck.value == user:
                    logging.getLogger('auth').debug('Authorized by cookie')
                    return cj

    if passwd is None:
        passwd = getpass.getpass('Input password: ')

    print 'authorization as %s with password %s...' % (user, '*'* len(passwd))
    logging.getLogger('auth').debug('real password is %s' % passwd)
    data = {
            'login':user,
            'passwd':passwd,
            'twoweeks':'yes'
            }
    opener.open("https://passport.yandex.ru/passport?mode=auth",
                       urllib.urlencode(data))
    if 'use_cookies_cache' in config():
        cj.save(ccache)
    return cj

def auth(user,password):
    logger = logging.getLogger('auth')
    cj = createAuthOpener(user, password)
    for cookie in cj:
        if cookie.name == "yandex_login":
            if cookie.value == user:
                logger.debug(cj)
                return cj
            else:
                cache = os.path.expanduser(COOKIES_CACHE)
                if os.path.exists(cache):
                    os.remove(cache)
    return None

def files_callback(option, opt_str, value, parser):
    assert value is None
    done = 0
    value = []
    rargs = parser.rargs
    while rargs:
        arg = rargs[0]

        if ((arg[:2] == "--" and len(arg) > 2) or
            (arg[:1] == "-" and len(arg) > 1 and arg[1] != "-")):
            break
        else:
            value.append(arg)
            del rargs[0]
    setattr(parser.values, option.dest, value)

def get_cookie(options):
    username = options.username
    if not username:
        if 'username' in config():
            username = config()['username']
        else:
            print 'Please, specify username'
            sys.exit(2)

    password = options.password
    if not password:
        if 'password' in config():
            password = config()['password']

    cookie = auth(username, password)
    return (username, cookie)


def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option( '-d', '--debug', dest='debug', action='store_true', help='Output debug information.', default=False)
    parser.add_option( '--version', dest='version', action='store_true', help='Show version number and quit.', default=False)
    parser.add_option( '-u', '--user', dest='username', help='Your Yandex login.', default=None)
    parser.add_option( '-p', '--pass', dest='password', help='Your password.', default=None)
    parser.add_option( '--albums', action='store_true', dest='album_list', help='Show album list.', default=False)
    parser.add_option( '-a', '--album', dest='album', type='int', help='Album to upload to.')
    parser.add_option( '--upload', dest='files', metavar='FILE LIST', action='callback', callback=files_callback, help='File list to upload' )
    (options, args) = parser.parse_args()

    if options.version:
        print('Python uploader for http://fotki.yandex.ru, version %s.' % VERSION)
        print('For more information and new versions, visit http://svetlyak.ru.')
        sys.exit(0)

    if options.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    (username, cookie) = get_cookie(options)
    if not cookie:
        print( 'Authorization error' )
        sys.exit(1)

    albums = get_albums( username, cookie )

    if options.album_list:
        print_albums( albums )
    else:
        if not options.album:
            print 'Please, specify an album\'s ID'
            print_albums( albums )
            sys.exit(2)

        for file in options.files:
            post(cookie, file, options.album, username)
        sys.exit(0)

if __name__ == "__main__":
    main()
