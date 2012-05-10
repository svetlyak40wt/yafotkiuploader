# -*- coding: utf-8 -*-

####
# 2008-2012 Alexander Artemenko <svetlyak.40wt@gmail.com>
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

import logging
import os, sys, re
import requests
import time

import anyjson as json


VERSION = (0, 3, 0)
if len(VERSION) == 3:
    __version__ = '%d.%d.%d' % VERSION
elif len(VERSION) == 4:
    __version__ = '%d.%d.%d-%s' % VERSION
else:
    __version__ = '.'.join(str(v) for v in VERSION)

API_URL = 'http://api-fotki.yandex.ru'

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


def smart_str(value):
    if isinstance(value, unicode):
        return value.encode('utf-8')
    return value


def smart_unicode(value):
    if isinstance(value, str):
        return value.decode('utf-8')
    return value


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
        return self._api.create_album(self.username,
                              title, summary)


class Entry(object):
    '''Base object for all atom entries.
       It holds all attributes and builds link map.'''
    fields = () # overwrite this to make these fields storable

    def __init__(self, api, entry):
        self._api = api
        self._entry = entry

        for key, value in entry.iteritems():
            if getattr(self, key, None) is None:
                setattr(self, key, value)

    def __repr__(self):
        return repr(self.__dict__)

    def save(self):
        entry = self._entry.copy()

        for key in self.fields:
            value = getattr(self, key, None)
            if value is not None:
                entry[key] = value

        if 'tags' in entry:
            entry['tags'] = dict((tag, '') for tag in entry['tags'])

        return self._api._post(
            self.links['edit'],
            data=entry,
            method='PUT',
        )

    def delete(self):
        self._api.delete_object(self.links['edit'])


class Photo(Entry):
    '''One photo.'''
    fields = ('title', 'tags', 'access', 'disable_comments',
              'xxx', 'hide_original', 'storage_private', 'summary')


    def __init__(self, *args, **kwargs):
        super(Photo, self).__init__(*args, **kwargs)
        self._atom_id = self.id
        self.id = int(self.id.split(':')[-1])

    def _get_tags(self):
        return self._tags

    def _set_tags(self, value):
        if isinstance(value, basestring):
            self._tags = [v.strip() for v in value.split(',')]
        else:
            self._tags = value.keys()

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


class Album(Entry):
    '''Album with some photos.'''
    fields = ('title', 'summary')

    def upload(self,
               filename,
               title=None,
               tags=None,
               description=None,
               access_type=ACCESS.PUBLIC,
               disable_comments=False,
               xxx=False,
               hide_orig=False,
               storage_private=False,
            ):

        return self._api.upload(self, filename, title, tags,
            description, access_type, disable_comments,
            xxx, hide_orig, storage_private)

    @property
    def photos(self):
        '''Returns iterator to all photos in this album.'''
        return self._api.get_photos(self.links['photos'])


class Api(object):
    def _build_absolute_url(self, url):
        return url.startswith('http') and url or (API_URL + url)

    def __init__(self, client_id, secret, token=None):
        self.client_id = client_id
        self.secret = secret
        self.token = token

    def _headers(self):
        headers = {'Accept': 'application/json'}
        if self.token:
            headers['Authorization'] = 'OAuth ' + self.token
        return headers

    def _get(self, url, parser = None):
        url = self._build_absolute_url(url)
        logging.debug('GET from %r' % url)
        response = requests.get(url, headers=self._headers())
        assert response.status_code == 200, response.content
        return json.loads(response.content)

    def _delete(self, url, parser = None):
        url = self._build_absolute_url(url)
        logging.debug('DELETE %r' % url)
        response = requests.delete(url, headers=self._headers())
        assert response.status_code == 204, response.content

    def _post(self, url, data=None, files=None, method='POST', extra_headers=None):
        url = self._build_absolute_url(url)

        headers = self._headers()

        if files is None:
            # Если файлов нет, то отправляем, как JSON,
            # в противном случае, отправляем, как Multipart
            data = json.dumps(data)
            headers['Content-type'] = 'application/json; charset=utf-8; type=entry'

        if extra_headers is not None:
            headers.update(extra_headers)

        logging.debug('%s to %r: %r' % (method, url, data))
        response = getattr(requests, method.lower())(url, data=data, files=files, headers=headers)
        assert response.status_code >= 200 and response.status_code < 300, response.content

        if response.status_code == 201:
            return self._get(response.headers['location'])

        return None

    def delete_object(self, url):
        return self._delete(url)

    def auth(self, username, password):
        self.username, self.password = username, password

        response = requests.post(
            'https://oauth.yandex.ru/token',
            data=dict(
                grant_type='password',
                username=username,
                password=password,
                client_id=self.client_id,
                client_secret=self.secret,
            ),
        )

        assert response.status_code == 200, response.content
        data = json.loads(response.content)
        self.token = data['access_token']
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
            data = self._get(url)
            for entry in data['entries']:
                yield cls(
                        self,
                        entry,
                    )
            url = data['links'].get('next')

    def get_albums(self, username):
        url = '/api/users/%s/albums/rpublished/' % username
        return self._get_object_list(url, Album)

    def get_photos(self, url):
        return self._get_object_list(url, Photo)

    def create_album(self, username, title, summary=''):
        title = title or 'Default'
        summary = summary or ''

        url = '/api/users/%s/albums/' % username
        entry = self._post(
            url,
            data=dict(
                title=smart_unicode(title),
                summary=smart_unicode(summary),
            )
        )

        return Album(self, entry)

    def upload(self, album, filename,
               title=None,
               tags=None,
               description=None,
               access_type=ACCESS.PUBLIC,
               disable_comments=False,
               xxx=False,
               hide_orig=False,
               storage_private=False,
               ):
        logging.debug('Uploading %r to album %s' % (filename, album))

        tags = tags or u''
        title = title or os.path.basename(filename)
        description = description or u''

        try:
            from pyexiv2 import Image as ImageExif
        except:
            logging.warning('can\'t find python-pyexiv2 library, exif extraction will be disabled.')
            ImageExif = None

        if ImageExif:
            try:
                exif = ImageExif(filename)
                try:
                    exif.readMetadata()
                    try: tags = tags or u','.join(t for t in (smart_unicode(tag) \
                                    for tag in exif['Iptc.Application2.Keywords']) if t)
                    except KeyError: pass
                    try: title = smart_unicode(title or exif['Iptc.Application2.ObjectName'])
                    except KeyError: pass
                    try: description = smart_unicode(description or \
                            exif['Iptc.Application2.Caption'])
                    except KeyError: pass
                    try: description = smart_unicode(description or \
                            exif['Exif.Image.ImageDescription'])
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
            title=smart_str(title),
            tags=smart_str(tags),
            description=smart_str(description),
            access_type=ACCESS.tostring(access_type),
            disable_comments=to_bool(disable_comments),
            xxx=to_bool(xxx),
            hide_orig=to_bool(hide_orig),
            storage_private=to_bool(storage_private),
            pub_channel='Python API',
            app_platform=sys.platform,
            app_version=__version__,
        )
        files = dict(
            image=open(smart_unicode(filename), 'rb'),
        )

        response = self._post(
            album.links['photos'],
            data=data,
            files=files,
            extra_headers=dict(
                Slug = os.path.basename(filename)
            ),
        )
        return Photo(self, response)

