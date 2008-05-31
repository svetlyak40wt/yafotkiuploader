#!/usr/bin/python
# -*- coding: utf-8 -*-

####
# 05/2008 Alexander Atemenko <svetlyak.40wt@gmail.com>
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
import os.path, sys, re
import urllib
from pdb import set_trace
from BeautifulSoup import BeautifulSoup

DEBUG = False

UPLOAD_URL='http://img.fotki.yandex.ru/modify'
ALBUMS_URL= 'http://fotki.yandex.ru/users/%s/albums/'

RET_URL = 'http://fotki.yandex.ru/actions/ajax_upload_fotka.xml'

def get_albums(username):
    all_albums_url = ALBUMS_URL % username
    doc = urllib2.urlopen( all_albums_url )
    soup = BeautifulSoup(doc)
    albums = soup.findAll('div', attrs={'class':'album'})
    result = []
    for album in albums:
        album = str(album.find('h3').find('a'))
        r = re.compile('.*/(\d+)/.*>(.*)</a>$')
        m = r.match( album )
        if m:
            result.append( (m.group(1), m.group(2)) )
    return result

def print_albums(albums):
    for album in albums:
        print '%s) %s' % album

def post_img(cookies,img,album):

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies), MultipartPostHandler.MultipartPostHandler)

        params = {
                'album' : str(album),
                'title' : os.path.basename(img),
#                'description': '',
                'tags': 'тест',
#                'xxx': '',
#                'mxxx': '',
#                'post2yaru': '',
#                'access': 'public',
#                'disable_comments': '',
                'image_source' : open(img, 'rb'),
                'retpage': RET_URL,
#                'ut': '1',
#                'source_login': 'art',
#                'source_type': 'profile',
#                'type': 'photo',
#                'replies': 'yes',
#                'idlist': '',
#                'xslt': 'no',
        }

        try:
                print opener.open(UPLOAD_URL, params).read()
        except urllib2.URLError, err:
                return err
                pass

def post(cookie,img,album):
        print 'post: %s,%s' % (album,img)
        print 'replay: %s' % post_img(cookie,img,album)

def createOpener(user, passwd):
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
    print 'authorization as %s with password %s...' % (user, passwd )
    data = {
            'login':user,
            'passwd':passwd,
            'twoweeks':'yes'
            }
    opener.open("http://passport.yandex.ru/passport?mode=auth",
                       urllib.urlencode(data))
    return cj

def auth(user,password):
    cj = createOpener(user, password)
    for cookie in cj:
        if cookie.name == "yandex_login":
            return cj
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

def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option( '-u', '--user', dest='username', help='Your Yandex login.')
    parser.add_option( '-p', '--pass', dest='password', help='Your password.')
    parser.add_option( '--albums', action='store_true', dest='album_list', help='Show album list.', default = False)
    parser.add_option( '-a', '--album', dest='album', type='int', help='Album to upload to.', default=1)
    parser.add_option( '--upload', dest='files', metavar='FILE LIST', action='callback', callback=files_callback, help='File list to upload' )
    (options, args) = parser.parse_args()

    if options.album_list:
        if not options.username:
            print 'Please, specify username to get album list'
            sys.exit(2)
        print_albums( get_albums( options.username ) )
    else:
        cookie=auth(options.username, options.password)
        if cookie:
            for file in options.files:
                post(cookie, file, options.album)
            sys.exit(0)
        else:
            print( 'authorization error' )
            sys.exit(1)

if __name__ == "__main__":
    main()
