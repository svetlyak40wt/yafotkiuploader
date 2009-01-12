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
import os, sys, re, md5
import urllib
import feedparser
import logging
import time
from datetime import datetime


from pdb import set_trace
from xml.dom import minidom
from lxml import etree as ET
from lxml.builder import ElementMaker
from StringIO import StringIO

_ATOM = 'http://www.w3.org/2005/Atom'
_ATOM_NS = '{%s}' % _ATOM
atom = ElementMaker(namespace = _ATOM)
namespaces = {
    'atom':  _ATOM,
    'app':   'http://www.w3.org/2007/app',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'f':     'yandex:fotki',
}

if feedparser._XML_AVAILABLE:
    class _FeedParserMixin(feedparser._FeedParserMixin):
        def _start_f_image_count(self, attrsD):
            context = self._getContext()
            context['image_count'] = int(attrsD['value'])
    setattr(_FeedParserMixin, '_start_f_image-count', _FeedParserMixin._start_f_image_count)

    class _StrictFeedParser(_FeedParserMixin, feedparser._StrictFeedParser):
        def __init__(self, baseuri, baselang, encoding):
            import xml.sax
            if feedparser._debug: sys.stderr.write('trying StrictFeedParser\n')
            xml.sax.handler.ContentHandler.__init__(self)
            _FeedParserMixin.__init__(self, baseuri, baselang, encoding)
            self.bozo = 0
            self.exc = None

    feedparser._StrictFeedParser = _StrictFeedParser

VERSION = (0, 3, 0, 'pre')
if len(VERSION) == 3:
    __version__ = '%d.%d.%d' % VERSION
elif len(VERSION) == 4:
    __version__ = '%d.%d.%d-%s' % VERSION
else:
    __version__ = '.'.join(str(v) for v in VERSION)

try:
    from pyexiv2 import Image as ImageExif
except:
    logging.warning('can\'t find python-pyexiv2 library, exif extraction will be disabled.')
    ImageExif = None

UPLOAD_URL = 'http://up.fotki.yandex.ru/upload'
API_URL = 'http://fimp.transvaal.yandex.ru'

class ACCESS:
    PUBLIC  = 1
    FRIENDS = 2
    PRIVATE = 3

    _str = {
        PUBLIC: 'public',
        FRIENDS: 'friends',
        PRIVATE: 'private',
    }
    _val = dict(map(reversed, _str.items()))

    @staticmethod
    def tostring(v):
        return ACCESS._str[v]

    @staticmethod
    def fromstring(v):
        return ACCESS._val[v]

def encrypt(text, key, b64encode=True):
    import os,  subprocess
    cmd = ['yamrsa-encrypt']
    if not b64encode:
        cmd.append('--no-b64encode')
    cmd.extend([str(key), text])
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    return p.stdout.read()

class FileNotFound(RuntimeWarning): pass
class NoPasswdOrCallback(RuntimeError): pass
class AuthError(RuntimeError): pass

class DeleteRequest(urllib2.Request):
    def get_method(self):
        return 'DELETE'
class PutRequest(urllib2.Request):
    def get_method(self):
        return 'PUT'

class User(object):
    def __init__(self, api, username):
        self._api = api
        self.username = username

    @property
    def albums(self):
        '''Returns iterator to user's albums.'''
        return self._api.get_albums(self.username)

    @property
    def photos(self):
        '''Returns iterator to all user's photos.'''
        url = '/api/users/%s/photos/' % self.username
        return self._api.get_photos(url)

    def get_photo(self, photo_id):
        '''Returns iterator to all user's photos.'''
        url = '/api/users/%s/photo/%d/' % (self.username, photo_id)
        photos = list(self._api.get_photos(url))
        return photos and photos[0] or None

    def create_album(self, title, summary = ''):
        self.albums.append(
            self._api.create_album(self.username,
                                  title, summary))

class AtomEntry(object):
    '''Base object for all atom entries.
       It holds all attributes and builds link map.'''
    fields = () # overwrite this to make these fields storable

    def __init__(self, api, entry, original_entry):
        self._api = api
        self._entry = entry
        self._original_entry = original_entry

        for key, value in entry.iteritems():
            if key.endswith('_parsed'):
                key = key[:-7]
                value = datetime(*value[:6])
            if key == 'links':
                value = dict((link['rel'], link) for link in value)
            if getattr(self, key, None) is None:
                setattr(self, key, value)

    def __repr__(self):
        return repr(self.__dict__)

    def save(self):
        orig = self._original_entry
        for field in self.fields:
            value = getattr(self, field, None)
            if value is not None:
                e_name = _ATOM_NS + field
                element = orig.find(e_name)
                if element is None:
                    element = ET.SubElement(orig, e_name)
                element.text = value

        return self._api._post_atom(self.links['edit']['href'],
                    data = ET.tostring(orig),
                    request_cls = PutRequest)

    def delete(self):
        self._api.delete_object(self.links['edit']['href'])


class Photo(AtomEntry):
    '''One photo.'''
    fields = ('title', 'tags', 'access', 'disable_comments',
              'xxx', 'hide_original', 'storage_private', 'yaru')


    def __init__(self, *args, **kwargs):
        super(Photo, self).__init__(*args, **kwargs)
        self._atom_id = self.id
        self.id = int(self.id.split(':')[-1])

    def _get_tags(self):
        return u', '.join(self._tags)
    def _set_tags(self, value):
        self._tags = [tag.strip() for tag in value.split(u',')]
    tags = property(_get_tags, _set_tags)

    @property
    def size(self):
        class helper(object):
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
            def __getattr__(self, k):
                return super(helper, self).__getattr__(k)()

        base_url = self.content[0].src
        gen_url = lambda size: lambda: re.sub('_[^_]+$', size, base_url)

        return helper(
            original = lambda: base_url,
            large = gen_url('_L'),
            medium = gen_url('_M'),
            small = gen_url('_S'),
            tiny = gen_url('_XS'),
            thumb = gen_url('_XXS'),
            small_thumb = gen_url('_XXXS'),
        )

    def save(self):
        orig = self._original_entry
        for tag in self._tags:
            ET.SubElement(orig, _ATOM_NS + 'category', dict(term = tag))
        return super(Photo, self).save()


class Album(AtomEntry):
    '''Album with some photos.'''
    fields = ('title', 'summary')

    def upload(self,
               photos,
               title = None,
               tags = None,
               description = None,
               access_type = ACCESS.PUBLIC,
               disable_comments = False,
               xxx = False,
               hide_orig = False,
               storage_private = False,
               yaru = True):

        album_id = self.id.split(':')[-1]
        for photo in photos:
            self._api.upload(album_id, photo, title, tags,
                description, access_type, disable_comments,
                xxx, hide_orig, storage_private, yaru)

    @property
    def photos(self):
        '''Returns iterator to all photos in this album.'''
        return self._api.get_photos(self.links['photos']['href'])


def _extract_original_entry(orig, entry):
    entries = orig.xpath('atom:entry[atom:id = $id]',
        id = entry.id, namespaces = namespaces)
    if len(entries) == 1:
        return entries[0]
    return None


class Api(object):
    def _build_absolute_url(self, url):
        return url.startswith('http') and url or (API_URL + url)

    def __init__(self):
        self.token = None
        self.opener = urllib2.build_opener(
            urllib2.HTTPCookieProcessor(),
            MultipartPostHandler.MultipartPostHandler)

    def _get(self, url, parser = ET.fromstring):
        url = self._build_absolute_url(url)
        logging.debug('GET from %r' % url)

        headers = {}
        if self.token is not None:
            headers['Authorization'] = 'FimpToken realm="fotki.yandex.ru", token="%s"' % self.token
        req = urllib2.Request(url, None, headers)

        original = self.opener.open(req).read()
        return parser(original), original

    def _get_atom(self, url):
        return self._get(url, feedparser.parse)

    def _post(self, url, data,
              content_type = 'application/atom+xml; type=entry',
              extra_headers = {},
              parser = ET.fromstring,
              request_cls = urllib2.Request):

        url = self._build_absolute_url(url)
        headers = {
            'Content-Type': content_type,
        }
        if self.token is not None:
            headers['Authorization'] = 'FimpToken realm="fotki.yandex.ru", token="%s"' % self.token
        headers.update(extra_headers)

        req = request_cls(url, data, headers)
        logging.debug('%s to %r: %r %r' % (req.get_method(), url, data, headers))
        try:
            data = self.opener.open(req).read()
        except urllib2.HTTPError, e:
            if e.code >= 200 and e.code < 300:
                data = e.read()
            else:
                logging.error('HTTPError, data: %r' % e.read())
                raise

        return parser(data)

    def _post_atom(self, url, data = {},
                   content_type = 'application/atom+xml; type=entry',
                   extra_headers = {},
                   request_cls = urllib2.Request):
        return self._post(url, data,
                content_type = content_type,
                extra_headers = extra_headers,
                parser = feedparser.parse,
                request_cls = request_cls)

    def delete_object(self, url):
        return self._post_atom(url, request_cls = DeleteRequest)

    def auth(self, username, password):
        self.username, self.password = username, password

        xml, original_xml = self._get('/fimp-key/')

        key = xml.find('key')
        request_id = xml.find('request_id')

        if key is None or request_id is None:
            raise Exception('Can\'t get public key.')

        credentials = '<credentials login="%s" password="%s"/>' % (self.username, self.password)
        credentials = encrypt(credentials, key.text)
        xml = self._post('/fimp-token/', dict(
                            credentials = credentials,
                            request_id = request_id.text))
        token = xml.find('token')
        if token is None:
            raise Exception('Can\'t get token.')

        self.token = token.text
        return self.token

    def find_user(self, username):
        return User(self, username)

    def _get_object_list(self, url, cls):
        '''Fetching objects from atom feeds.
           This method accepts URL and object's class.
           Class contructors must receive Atom Entry object and original
           entry, parsed by ElementTree.
        '''

        while url is not None:
            feed, original_feed = self._get_atom(url)
            original_feed = ET.fromstring(original_feed)
            for entry in feed['entries']:
                yield cls(
                        self,
                        entry,
                        original_entry = _extract_original_entry(original_feed, entry)
                    )
            url = None
            links = getattr(feed['feed'], 'links', [])
            for link in links:
                if link['rel'] == 'next':
                    url = link['href']

    def get_albums(self, username):
        url = '/api/users/%s/albums/rpublished/' % username
        return self._get_object_list(url, Album)

    def get_photos(self, url):
        return self._get_object_list(url, Photo)

    def create_album(self, username, title, summary = ''):
        title = title or 'Default'
        summary = summary or ''
        xml = ET.tostring(
                atom.entry(
                    atom.title(title.decode('utf-8')),
                    atom.summary(summary.decode('utf-8'))))

        feed, original_feed = self._post_atom('/api/users/%s/albums/' % username, xml)
        original_feed = ET.fromstring(original_feed)
        original_entry = _extract_original_entry(original_feed, entry)
        return Album(self, feed['entries'][0], original_entry)

    def upload(self, album_id, filename,
               title = None, tags = None,
               description = None,
               access_type = ACCESS.PUBLIC,
               disable_comments = False,
               xxx = False,
               hide_orig = False,
               storage_private = False,
               yaru = True,
               ):
        logging.debug('Uploading %r to album with id %r' % (filename, album_id))

        tags = tags or u''
        title = title or os.path.basename(filename)
        description = description or u''

        if ImageExif:
            try:
                exif = ImageExif(filename)
                try:
                    exif.readMetadata()
                    try: tags = tags or u','.join(t for t in (tag.decode('utf8', 'ignore') \
                                    for tag in exif['Iptc.Application2.Keywords']) if t)
                    except KeyError: pass
                    try: title = title or exif['Iptc.Application2.ObjectName'].decode('utf8', 'ignore')
                    except KeyError: pass
                    try: description = description or \
                            exif['Iptc.Application2.Caption'].decode('utf8', 'ignore')
                    except KeyError: pass
                    try: description = description or \
                            exif['Exif.Image.ImageDescription'].decode('utf8', 'ignore')
                    except KeyError: pass
                except IOError:
                    pass
            except IOError:
                pass

        def to_bool(value, yes = 'true', no = 'false'):
            if value in [True, 'yes', 1, 'true']:
                return yes
            return no

        data = dict(
            image = open(filename, 'rb'),
            title = title.encode('utf8'),
            tags = tags.encode('utf8'),
            description = description.encode('utf8'),
            access_type = ACCESS.tostring(access_type),
            album = str(album_id),
            disable_comments = to_bool(disable_comments),
            xxx = to_bool(xxx),
            hide_orig = to_bool(hide_orig),
            storage_private = to_bool(storage_private),
            yaru = to_bool(yaru, '1', '0'),
            pub_channel = 'Python API',
            app_platform = sys.platform,
            app_version = __version__,
        )

        print 'Photo: %r' % (self._post('/fimp/post/', data,
            extra_headers = dict(
                Slug = os.path.basename(filename)),
            parser = lambda x: x))

