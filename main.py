#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import webapp2
import json
import urllib
import re
import logging

from data_class import Stream, StreamInfo, ShowStream, Image, User
from datetime import datetime
from google.appengine.api import users
from google.appengine.api import images
from random import randrange

from google.appengine.api import mail
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext import db
import jinja2
from collections import OrderedDict

import threading

REPORT_RATE_MINUTES = "0"
LAST_REPORT = None
INDEX = 0
INDEX1 = 2

#SERVICES_URL = 'http://localhost:8000/'
SERVICES_URL = 'http://apt-final-project-test.appspot.com/'


default_preface = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQ3DFxGhXSmn0MHjbEEtw-0N9sDKhyIP7tM_r3Wo1mY7WhY2xvZ"
default_photo = "http://www.wikihow.com/images/f/ff/Draw-a-Cute-Cartoon-Person-Step-14.jpg"
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


#NAV_LINKS = sorted(('Create', 'View', 'Search', 'Trending', 'My Places of Interest'))
#NAV_LINKS = OrderedDict(zip(NAV_LINKS, map(lambda x: '/'+x.lower(), NAV_LINKS) ))

NAV_LINKS = {'Create': '/create', 'Friends': '/view', 'Search': '/search', 'Trending': '/trending',
             'My Places of Interest': '/manage'}
USER_NAV_LINKS = NAV_LINKS.copy()

WEBSITE = 'https://blueimp.github.io/jQuery-File-Upload/'
MIN_FILE_SIZE = 1  # bytes
MAX_FILE_SIZE = 5000000  # bytes
IMAGE_TYPES = re.compile('image/(gif|p?jpeg|(x-)?png)')
ACCEPT_FILE_TYPES = IMAGE_TYPES
THUMBNAIL_MODIFICATOR = '=s80'  # max width / height
EXPIRATION_TIME = 300  # seconds


class UploadImageHandler(webapp2.RequestHandler):
    def initialize(self, request, response):
        super(UploadImageHandler, self).initialize(request, response)
        self.response.headers['Access-Control-Allow-Origin'] = '*'
        self.response.headers[
            'Access-Control-Allow-Methods'
        ] = 'OPTIONS, HEAD, GET, POST, PUT, DELETE'
        self.response.headers[
            'Access-Control-Allow-Headers'
        ] = 'Content-Type, Content-Range, Content-Disposition'

    def json_stringify(self, obj):
        return json.dumps(obj, separators=(',', ':'))

    def validate(self, file):
        if file['size'] < MIN_FILE_SIZE:
            file['error'] = 'File is too small'
        elif file['size'] > MAX_FILE_SIZE:
            file['error'] = 'File is too big'
        elif not ACCEPT_FILE_TYPES.match(file['type']):
            file['error'] = 'Filetype not allowed'
        else:
            return True
        return False

    def get_file_size(self, file):
        file.seek(0, 2)  # Seek to the end of the file
        size = file.tell()  # Get the position of EOF
        file.seek(0)  # Reset the file position to the beginning
        return size

    def options(self):
        pass

    def head(self):
        pass

    def post(self):
        pictures = self.request.get_all('files[]')
        results = []
        if len(pictures) > 0:
            stream_id = self.request.get('stream_id')
            # print "stream name is ", stream_id

            for image in pictures:
                Stream.insert_with_lock(stream_id, image)
                results.append({'name': '', 'url': '', 'type': '', 'size': 0})

        s = json.dumps({'files': results}, separators=(',', ':'))
        self.response.headers['Content-Type'] = 'application/json'
        # print "duming material is ", s
        return self.response.write(s)


class MainPage(webapp2.RequestHandler):
    def get(self):
        print "aaaaaaaaa"
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            print 'i am here'
            url = users.create_login_url('/manage')
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': self.request.get('user_id'),
            'url': url,
            'url_linktext': url_linktext,
        }

        #add user to user pool
        user = str(users.get_current_user()).lower()
        exist = False
        people = User.query(User.user_id != '').fetch()
        print 'current user is ', user
        for person in people:
            print "already users are ", person.user_id
            if person.user_id == user:
                exist = True

        if not exist:
            new_user = User(user_id=user)
            new_user.put()
        print "add user into user pool"

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


class LoginHandler(webapp2.RequestHandler):
    def get(self):
        print "bbbbbbbbbb"
        user = str(users.get_current_user()).lower()
        if user:
            self.response.headers['Content-Type'] = 'text/html; charset=utf-8'
            self.response.write('Hello, ' + user.nickname())
        else:
            self.redirect(users.create_login_url(self.request.uri))

        self.redirect('/manage')


class ManageHandler(webapp2.RequestHandler):
    def get(self):
        user = str(users.get_current_user()).lower()
        print 'user is ', user
        subscribed_streams = []
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        if len(qry) > 0:
            for key in qry[0].subscribed:
                subscribed_streams.append(key.get())

        print subscribed_streams

        streams = Stream.query(Stream.stream_id != '').fetch()
        image_url = []
        for stream in streams:
            #print stream.stream_id
            #print user
            if stream.user_id == user:
                if stream.cover_url:
                    image_url.append([stream.cover_url, stream.stream_id])
                else:
                    image_url.append([default_preface, stream.stream_id])


        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': str(users.get_current_user()).lower(),
            'user_streams': Stream.query(Stream.owner == str(user)).fetch(),
            'subscribed_streams': subscribed_streams,
            'usr': user,
            'image_url': image_url,
        }

        # all_streams = Stream.query(Stream.stream_id != '').fetch()
        # for s in all_streams:
        #     print s.stream_id
        #
        # print 'length of user_stream', len(template_values['user_streams'])
        # print 'length of subscribed streams', len(template_values['subscribed_streams'])

        template = JINJA_ENVIRONMENT.get_template('manage.html')
        self.response.write(template.render(template_values))
        print "in manage page, "

    def post(self):
        form = {'stream_id': self.request.get_all('stream_id'),
                'user': str(users.get_current_user()).lower(),
                }

        print "creating post is activated"
        form_data = json.dumps(form)
        if self.request.get('delete'):
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'delete_a_stream',
                                    method=urlfetch.POST, headers={'Content-Type': 'application/json'})
        if self.request.get('unsubscribe'):
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'unsubscribe_a_stream',
                                    method=urlfetch.POST, headers={'Content-Type': 'application/json'})
        self.redirect('/manage')


class CreateHandler(webapp2.RequestHandler):
    def get(self):
        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': self.request.get('user_id'),
        }

        print template_values['user_id']
        template = JINJA_ENVIRONMENT.get_template('create.html')
        self.response.write(template.render(template_values))

    def post(self):
        print 'creating stream now'
        user = str(users.get_current_user()).lower()
        stream_id = self.request.get('stream_id')
        latitude = self.request.get('latitude')
        longitude = self.request.get('longitude')

        print 'first', stream_id
        streams = Stream.query(Stream.stream_id != '').fetch()
        for stream in streams:
            print 'hi', stream.stream_id
            if stream.stream_id == stream_id:
                info = {'error': 'you tried to create a stream whose name already existed'}
                info = urllib.urlencode(info)
                self.redirect('/error?'+info)
                return

        if self.request.get("subscribers"):
            mail.send_mail(sender=str(user)+"<"+str(user)+"@gmail.com>",
                           to="<"+self.request.get("subscribers")+">",
                           subject="Please subscribe my stream",
                           body=self.request.get("message"))

        form = {'stream_id': self.request.get('stream_id'),
                'user_id': str(users.get_current_user()).lower(),
                'tags': self.request.get('tags'),
#               'subscribers': self.request.get('subscribers'),
                'cover_url': self.request.get('cover_url'),
                'owner': str(users.get_current_user()).lower(),
                'views': 0,
                'latitude': latitude,
                'longitude': longitude,
                }

        print "aaaaaaa"
        form_data = json.dumps(form)
        result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'create_a_new_stream',
                                method=urlfetch.POST, headers={'Content-Type': 'application/json'})
        print "bbbbbbb"
        self.redirect('/manage')


class ViewSingleHandler(webapp2.RequestHandler):
    def get(self):
        user = str(users.get_current_user()).lower()
        stream_id = self.request.get('stream_id')
        print 'stream id is', stream_id
        info = {'stream_id': self.request.get('stream_id')}
        info = urllib.urlencode(info)

#       we should use the actual user
        user_streams = Stream.query(Stream.stream_id == stream_id).fetch()
        image_url = [""] * 3

        stream = user_streams[0]
        owner = stream.owner
        print 'stream id is', stream.stream_id
        if owner != str(user):
            stream.views += 1
            while len(stream.view_queue) > 0 and (datetime.now() - stream.view_queue[0]).seconds > 3600:
                del stream.view_queue[0]
            stream.view_queue.append(datetime.now())
            stream.put()

        #get first three pictures
        counter = 0
        has_image = True
        image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                  db.Key.from_path('Stream', stream.stream_id))

        print "type of gqlquery", type(image_query)
        for image in image_query[0:stream.num_images]:
            image_url[counter] = "image?image_id=" + str(image.key())
            counter += 1
            if counter == 3:
                break

        print "image url is", image_url
        #calculate hasSub
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        has_sub = False
        if len(qry) == 0:
            has_sub = False
        else:
            for key in qry[0].subscribed:
                if key.get().stream_id == stream_id:
                    has_sub = True
                    break
        upload_url = ''
        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'owner': owner,         #the owner of the stream
            'user': str(users.get_current_user()).lower(),   #current user
            'upload_url': upload_url,
            'image_url': image_url,
            'has_image': has_image,
            'hasSub': has_sub,
            'stream_id': stream_id,
        }

        print "owner is ", template_values['owner']
        print "user is ", template_values['user']
        template = JINJA_ENVIRONMENT.get_template('viewstream.html')
        self.response.write(template.render(template_values))

    def post(self):
        form = {'user': str(users.get_current_user()).lower(),}
        if self.request.get('Subscribe') == 'Subscribe':
            form['stream_id'] = self.request.get('stream_id')
            form_data = json.dumps(form)
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'subscribe_a_stream',
                               method=urlfetch.POST, headers={'Content-Type': 'application/json'})
        elif self.request.get('Subscribe') == 'Unsubscribe':
            form['stream_id'] = self.request.get_all('stream_id')
            form_data = json.dumps(form)
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'unsubscribe_a_stream',
                                    method=urlfetch.POST, headers={'Content-Type': 'application/json'})

        if self.request.get('more'):
            info = {'stream_id': self.request.get('stream_id')}
            info = urllib.urlencode(info)
            self.redirect('/view_more?'+info)
        else:
            self.redirect('/manage')


class ViewStreamHandler(webapp2.RequestHandler):
    def get(self):
        user = str(users.get_current_user()).lower()
        stream_id = self.request.get('stream_id')
        print 'stream id is', stream_id
        info = {'stream_id': self.request.get('stream_id')}
        info = urllib.urlencode(info)

#       we should use the actual user
        user_streams = Stream.query(Stream.stream_id == stream_id).fetch()
        image_url = [""]*3
        hidden_image = []

        stream = user_streams[0]
        owner = stream.owner
        print 'stream id is', stream.stream_id
        if owner != str(user):
            stream.views += 1
            while len(stream.view_queue) > 0 and (datetime.now() - stream.view_queue[0]).seconds > 3600:
                del stream.view_queue[0]
            stream.view_queue.append(datetime.now())
            stream.put()

        #get first three pictures
        counter = 0
        has_image = True
        has_hidden = len(hidden_image)>0
        image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                  db.Key.from_path('Stream', stream.stream_id))

        logging.debug("type of gqlquery is %s", type(image_query))
        maxdate = None
        mindate = None
        for image in image_query[0:stream.num_images]:
            d = dict()
            d["url"] = "image?image_id=" + str(image.key())
            d["lat"] = str(image.geo_loc.lat)
            d["long"] = str(image.geo_loc.lon)
            date = str.split(str(image.upload_date))
            dateint = int(date[0].replace("-",""))
            d["time"] = dateint
            if maxdate == None or dateint > maxdate:
                maxdate = dateint
            if mindate==None or dateint < mindate:
                mindate = dateint
            if counter < 3:
                image_url[counter] = d
            else:
                hidden_image.append(d)
            counter += 1

        #calculate hasSub
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        has_sub = False
        if len(qry) == 0:
            has_sub = False
        else:
            for key in qry[0].subscribed:
                if key.get().stream_id == stream_id:
                    has_sub = True
                    break
        upload_url = ''
        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'owner': owner,         #the owner of the stream
            'user': str(users.get_current_user()).lower(),   #current user
            'upload_url': upload_url,
            'image_url': image_url,
            'hidden_image':hidden_image,
            'has_image': has_image,
            'hasSub': has_sub,
            'stream_id': stream_id,
            'has_hidden':has_hidden,
            'maxdate':maxdate,
            'mindate':mindate
        }

        print "owner is ", template_values['owner']
        print "user is ", template_values['user']
        template = JINJA_ENVIRONMENT.get_template('viewstream.html')
        self.response.write(template.render(template_values))

    def post(self):
        form = {'user': str(users.get_current_user()).lower(),}
        if self.request.get('Subscribe') == 'Subscribe':
            form['stream_id'] = self.request.get('stream_id')
            form_data = json.dumps(form)
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'subscribe_a_stream',
                               method=urlfetch.POST, headers={'Content-Type': 'application/json'})
        elif self.request.get('Subscribe') == 'Unsubscribe':
            form['stream_id'] = self.request.get_all('stream_id')
            form_data = json.dumps(form)
            result = urlfetch.fetch(payload=form_data, url=SERVICES_URL + 'unsubscribe_a_stream',
                                    method=urlfetch.POST, headers={'Content-Type': 'application/json'})

        if self.request.get('more'):
            info = {'stream_id': self.request.get('stream_id')}
            info = urllib.urlencode(info)
            self.redirect('/view_more?'+info)
        else:
            self.redirect('/manage')


class ViewUserHandler(webapp2.RequestHandler):
    def get(self):
        user = self.request.get('user_id')
        print 'user is ', user
        subscribed_streams = []
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        if len(qry) > 0:
            for key in qry[0].subscribed:
                subscribed_streams.append(key.get())

        print subscribed_streams

        streams = Stream.query(Stream.stream_id != '').fetch()
        image_url = []
        for stream in streams:
            #print stream.stream_id
            #print user
            if stream.user_id == user:
                if stream.cover_url:
                    image_url.append([stream.cover_url, stream.stream_id])
                else:
                    image_url.append([default_preface, stream.stream_id])


        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': str(users.get_current_user()).lower(),
            'user_streams': Stream.query(Stream.owner == str(user)).fetch(),
            'subscribed_streams': subscribed_streams,
            'usr': user,
            'image_url': image_url,
        }

        template = JINJA_ENVIRONMENT.get_template('viewuser.html')
        self.response.write(template.render(template_values))



class ViewImageHandler(webapp2.RequestHandler):
    def get(self):
        img = db.get(self.request.get('image_id'))
        self.response.out.write(img.image)
# get the whole image object

class ViewImageObjectHandler(webapp2.RequestHandler):
    def get(self):
        img = db.get(self.request.get('image_id'))
        self.response.out.write(img)


class ViewAllFriendHandler(webapp2.RequestHandler):
    def get(self):
        print 'showing friends'
        user = str(users.get_current_user()).lower()
        cur_user = User.query(User.user_id == user).fetch()[0]
        image_url = []
        for friend in cur_user.friends:
            friend_object = User.query(User.user_id == friend).fetch()[0]
            if friend_object.photo:
                image_url.append([friend_object.photo, friend_object.user_id])
            else:
                image_url.append([default_photo, friend_object.user_id])

        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user': self.request.get('user'),
            'image_url': image_url,
        }

        template = JINJA_ENVIRONMENT.get_template('viewall.html')
        self.response.write(template.render(template_values))


    def post(self):
        print "i am adding friend "
        pattern = self.request.get('query')
        print "add friend query is ", pattern

        user = str(users.get_current_user()).lower()
        me = User.query(User.user_id == user).fetch()[0]

        people = User.query(User.user_id != '').fetch()

        exist = False
        if pattern:
            for person in people:
                if person.user_id == pattern:
                    exist = True
                    print "exiting is true..."
                    #add to my friend list
                    is_friend = False
                    for my_friend in me.friends:
                        if my_friend == pattern:
                            is_friend = True

                    if not is_friend:
                        print "is adding friends"
                        me.friends.append(pattern)

        if not exist:
            print "not existing"

        me.put()
        self.redirect('/view')


class GeoMapHandler(webapp2.RequestHandler):
    def get(self):
        streams = Stream.query(Stream.stream_id != '').fetch()
        image_info = []
        for stream in streams:
            image_info.append([stream.cover_url, stream.stream_id])
        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
        }

        template = JINJA_ENVIRONMENT.get_template('geomap.html')
        self.response.write(template.render(template_values))


class ViewMoreHandler(webapp2.RequestHandler):
    def get(self):
        user = str(users.get_current_user()).lower()
        stream_id = self.request.get('stream_id')
        print 'stream id is', stream_id
        info = {'stream_id': self.request.get('stream_id')}
        info = urllib.urlencode(info)
#       we should use the actual user
        user_streams = Stream.query(Stream.stream_id == stream_id).fetch()

        stream = user_streams[0]
        owner = stream.owner
        print 'stream id is', stream.stream_id
        if owner != str(user):
            stream.views += 1
            stream.view_queue.append(datetime.now())
            stream.put()

        has_image = True
        image_url = []
        image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                  db.Key.from_path('Stream', stream.stream_id))

        # for image in image_query[0: len(stream.image_list)]:
        for image in image_query[0:stream.num_images]:
            d = dict()
            d["url"] = "image?image_id=" + str(image.key())
            d["lat"] = str(image.geo_loc.lat)
            d["long"] = str(image.geo_loc.lon)
            image_url.append(d)

        #calculate hasSub
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        has_sub = False
        if len(qry) == 0:
            has_sub = False
        else:
            for key in qry[0].subscribed:
                if key.get().stream_id == stream_id:
                    has_sub = True
                    break


        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'owner': owner,         #the owner of the stream
            'user': str(users.get_current_user()).lower(),   #current user
            'image_url': image_url,
            'has_image': has_image,
            'hasSub': has_sub,
            'stream_id': stream_id,
        }

        print "owner is ", template_values['owner']
        print "user is ", template_values['user']
        template = JINJA_ENVIRONMENT.get_template('viewMoreWithMap.html')
        self.response.write(template.render(template_values))


class SearchHandler(webapp2.RequestHandler):
    def get(self):
        pattern = self.request.get("qry")
        print pattern
        all_streams = Stream.query(Stream.stream_id != '').fetch()
        search_result = []
        if pattern:
            for stream in all_streams:
                if pattern in stream.stream_id:
                    stream_id = stream.stream_id
                    if stream.cover_url != '':
                        image_url = stream.cover_url
                    else:
                        image_url = "https://encrypted-tbn0.gstatic.com/images?" + \
                                    "q=tbn:ANd9GcQ3DFxGhXSmn0MHjbEEtw-0N9sDKhyIP7tM_r3Wo1mY7WhY2xvZ"
                    result = ShowStream(image_url, 0, stream_id)
                    search_result.append(result)

        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': self.request.get('user_id'),
            'query_results': search_result,
        }

        template = JINJA_ENVIRONMENT.get_template('search.html')
        self.response.write(template.render(template_values))

    def post(self):
        print "searching "
        info = {'qry': self.request.get('query')}
        self.redirect('/search?'+urllib.urlencode(info))


class AddFriendHandler(webapp2.RequestHandler):
    def post(self):
        print "i am adding friend "
        pattern = self.request.get('query')
        print "add friend query is ", pattern
        people = User.query(User.user_id != '').fetch()

        exist = False
        if pattern:
            for person in people:
                if person.user_id == pattern:
                    exist = True
                    #add to my friend list

        if not exist:
            print "hellp"


class TrendingHandler(webapp2.RequestHandler):
    def get(self):
        print "updating top 3 popular streams"
        first_three = []
        all_streams = Stream.query(Stream.stream_id != '').fetch()
        mycmp = lambda x, y: (len(y.view_queue) - len(x.view_queue))
        all_streams.sort(mycmp)
        size = 3 if (len(all_streams) - 3) > 0 else len(all_streams)
        print size
        for i in range(size):
            stream = all_streams[i]
            #print "current stream is", stream
            views = len(stream.view_queue)
            stream_id = stream.stream_id
            if stream.cover_url != '':
                image_url = stream.cover_url
            else:
                image_url = "https://encrypted-tbn0.gstatic.com/images?" + \
                            "q=tbn:ANd9GcQ3DFxGhXSmn0MHjbEEtw-0N9sDKhyIP7tM_r3Wo1mY7WhY2xvZ"

            trending_stream = ShowStream(image_url, views, stream_id)

            print "current trending stream is", trending_stream
            first_three.append(trending_stream)
            print trending_stream.url
        print "end for loop"

        checked = [""] * 4
        cur_rate = REPORT_RATE_MINUTES;

        if cur_rate:
            if cur_rate == '0':
                checked[0] = "checked=checked"
            elif cur_rate == '5':
                checked[1] = "checked=checked"
            elif cur_rate == '60':
                checked[2] = "checked=checked"
            elif cur_rate == '1440':
                checked[3] = "checked=checked"
        else:
            checked[0] = "checked=checked"

        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': self.request.get('user_id'),
            'streams': first_three,
            'checked': checked,
        }

        template = JINJA_ENVIRONMENT.get_template('trending.html')
        self.response.write(template.render(template_values))

    def post(self):
        print 'in treading post'
        rate = self.request.get('rate')
        global REPORT_RATE_MINUTES
        REPORT_RATE_MINUTES = rate
        self.redirect('/trending')


class ErrorHandler(webapp2.RequestHandler):
    def get(self):
        error_msg = self.request.get('error')
        template_values = {
            'nav_links': USER_NAV_LINKS,
            'path': os.path.basename(self.request.path).capitalize(),
            'user_id': self.request.get('user_id'),
            'error': error_msg,
        }

        template = JINJA_ENVIRONMENT.get_template('error.html')
        self.response.write(template.render(template_values))


#############################################################################################
class CreateANewStreamHandler(webapp2.RequestHandler):
    def post(self):
        print "inside create a new stream"
        data = json.loads(self.request.body)
        user = data['user_id']
        longitude = data['longitude']
        latitude = data['latitude']
        print user, ' is creating'
        new_stream = Stream(parent=ndb.Key('User', user),
                            stream_id=data['stream_id'],
                            user_id=data['user_id'],
                            tags=data['tags'],
                            cover_url=data['cover_url'] if 'cover_url' in data else '',
                            views=0,
                            num_images=0,
                            last_add=str(datetime.now()),
                            owner=data['owner'],
                            )

        if longitude == '' or latitude == '':
            new_stream.geo_loc = ndb.GeoPt(randrange(-10,10),randrange(-10,10))
        else:
            new_stream.geo_loc = ndb.GeoPt(float(latitude), float(longitude))

        new_stream.put()
        result = json.dumps({'status': '0'})
        self.response.write(result)


class DeleteStreamHandler(webapp2.RequestHandler):
    def post(self):
        print "************delete stream******************"
        data = json.loads(self.request.body)
        user = data['user']
        for stream_id in data['stream_id']:
            qry = Stream.query(Stream.stream_id == stream_id).fetch()
            if len(qry) > 0:
                #delete all the images in this stream
                image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                          db.Key.from_path('Stream', stream_id))
                for image in image_query[0:qry[0].num_images]:
                    image.delete()
                    print "******************delete images"

                Stream.reset_image_num(qry[0].stream_id)
                #delete stream
                qry[0].key.delete()

        self.redirect('/manage')


class SubscribeStreamHandler(webapp2.RequestHandler):
    def post(self):
        data = json.loads(self.request.body)
        user = data['user']
        stream_id = data['stream_id']
        print stream_id, 'hello'
        qry = Stream.query(Stream.stream_id == stream_id).fetch()
        print 'lenght of qry is ', len(qry)

        ancestor_key = ndb.Key('User', user)
        stream_info = StreamInfo.query_stream(ancestor_key).fetch()
        if len(stream_info) == 0:
            print 'create a new stream_info'
            new_stream_info = StreamInfo(parent=ndb.Key('User', user))
            new_stream_info.subscribed.insert(0, qry[0].key)
            new_stream_info.put()
        else:
            new_stream_info = stream_info[0]
            new_stream_info.subscribed.insert(0, qry[0].key)
            new_stream_info.put()

        print 'finished'
        self.redirect('/manage')


class UnsubscribeStreamHandler(webapp2.RequestHandler):
    def post(self):
        print 'in unsubscribe handler'
        data = json.loads(self.request.body)
        user = data['user']
        ancestor_key = ndb.Key('User', user)
        stream_info = StreamInfo.query_stream(ancestor_key).fetch()
        print stream_info[0].subscribed
        print data['stream_id']
        for stream_id in data['stream_id']:
            for key in stream_info[0].subscribed:
                print "here is ", key.get().stream_id, stream_id
                if key.get().stream_id == stream_id:
                    stream_info[0].subscribed.remove(key)
                    stream_info[0].put()       #remember to put it back in ndbstore
                    break

        self.redirect('/manage')


class ReportHandler(webapp2.RequestHandler):
    def get(self):
        print 'in report handler', str(users.get_current_user()).lower()
        print "NOW RATE BECOMES", REPORT_RATE_MINUTES
        if REPORT_RATE_MINUTES == '0':
            return

        global LAST_REPORT
        if not LAST_REPORT:
            LAST_REPORT = datetime.now()
            print "because LAST_REPORT is not set, i return"
            return

        delta = (datetime.now() - LAST_REPORT).seconds
        if delta < int(REPORT_RATE_MINUTES) * 60:
            print "because delta is not enough, i return"
            return

        LAST_REPORT = datetime.now()

        #get trending information to send
        first_three = []
        all_streams = Stream.query(Stream.stream_id != '').fetch()
        mycmp = lambda x, y: (len(y.view_queue) - len(x.view_queue))
        all_streams.sort(mycmp)
        size = 3 if (len(all_streams) - 3) > 0 else len(all_streams)
        print size
        for i in range(size):
            stream = all_streams[i]
            print "current stream is", stream.stream_id
            views = len(stream.view_queue)
            stream_id = stream.stream_id
            if stream.cover_url != '':
                image_url = stream.cover_url
            else:
                image_url = "https://encrypted-tbn0.gstatic.com/images?" \
                            "q=tbn:ANd9GcQ3DFxGhXSmn0MHjbEEtw-0N9sDKhyIP7tM_r3Wo1mY7WhY2xvZ"

            trending_stream = ShowStream(image_url, views, stream_id)
            print "current trending stream is", trending_stream
            first_three.append(trending_stream)
            print trending_stream.url
        print "end for loop"

        message = "Top three trending streams:"
        for element in first_three:
            message += element.stream_id + " viewed by " + str(element.views) + " times; "

        print "message is *******************", message
        mail.send_mail(sender="libo <chenlibo0928@gmail.com>",
                       to="<nima.dini@utexas.edu>",
                       subject="Trending Report",
                       body=message)
        print message
        return


class AutoCompleteHandler(webapp2.RequestHandler):
    def get(self):
        pattern = self.request.get("term")
        print pattern
        all_streams = Stream.query(Stream.stream_id != '').fetch()
        ret_tags = []
        if pattern:
            for stream in all_streams:
                if pattern in stream.tags:
                    ret_tags.append(stream.tags)

        ret_tags.sort();
        if len(ret_tags) == 0:
            ready = False
        else:
            ready = True

        context = {"ready": ready, "tags": ret_tags}
        print context
        self.response.write(json.dumps(context))


################################ FOR PHASE 3 Android PART #############################
class AndroidCreateANewStreamHandler(webapp2.RequestHandler):
    def post(self):
        print "inside android create a new stream"
        stream_id = self.request.get('stream_id')
        user_id = self.request.get('user_id')
        longitude = self.request.get('longitude')
        latitude = self.request.get('latitude')
        print user_id, ' is creating in android'
        new_stream = Stream(parent=ndb.Key('User', user_id),
                            stream_id=stream_id,
                            user_id=user_id,
                            views=0,
                            num_images=0,
                            last_add=str(datetime.now()),
                            )

        if longitude == '' or latitude == '':
            new_stream.geo_loc = ndb.GeoPt(randrange(-10,10),randrange(-10,10))
        else:
            new_stream.geo_loc = ndb.GeoPt(float(latitude), float(longitude))

        new_stream.put()
        result = json.dumps({'status': '0'})
        self.response.write(result)


class AndroidViewAllStreamsHandler(webapp2.RequestHandler):
    def get(self):
        streams = Stream.query(Stream.stream_id != '').fetch()
        print type(streams)
        stream_url = []
        stream_ids = []
        for stream in streams:
            stream_ids.append(stream.stream_id)
            if stream.cover_url:
                stream_url.append(stream.cover_url)
            else:
                stream_url.append(default_preface)

        name = self.request.get('user_id')
        print "adroid user is ", name
        dict_passed = {'displayImages': stream_url, 'streamId': stream_ids, 'name': name}
        json_obj = json.dumps(dict_passed, sort_keys=True, indent=4, separators=(',', ': '))
        self.response.write(json_obj)


class AndroidViewStreamHandler(webapp2.RequestHandler):
    def get(self):
        user = self.request.get('user_id')
        stream_id = self.request.get('stream_id')
        print 'stream id is', stream_id
#       we should use the actual user
        user_streams = Stream.query(Stream.stream_id == stream_id).fetch()

        stream = user_streams[0]
        owner = stream.owner
        print 'stream id is', stream.stream_id
        my_own = True
        if owner != str(user):
            my_own = False
            stream.views += 1
            stream.view_queue.append(datetime.now())
            stream.put()

        image_url = []
        image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                  db.Key.from_path('Stream', stream.stream_id))

        # for image in image_query[0: len(stream.image_list)]:
        for image in image_query[0:stream.num_images]:
            d = dict()
            d["url"] = SERVICES_URL +"image?image_id=" + str(image.key())
            d["lat"] = str(image.geo_loc.lat)
            d["long"] = str(image.geo_loc.lon)
            image_url.append(d)

        #calculate hasSub
        qry = StreamInfo.query_stream(ndb.Key('User', str(user))).fetch()
        has_sub = False
        if len(qry) == 0:
            has_sub = False
        else:
            for key in qry[0].subscribed:
                if key.get().stream_id == stream_id:
                    has_sub = True
                    break

        dict_passed = {'displayImages': image_url, 'myOwn': my_own, 'hasSub': has_sub}
        json_obj = json.dumps(dict_passed, sort_keys=True, indent=4, separators=(',', ': '))
        self.response.write(json_obj)


class AndroidViewNearby(webapp2.RequestHandler):
    def get(self):
        target_long = float(self.request.get('longitude'))
        target_lat = float(self.request.get('latitude'))
        streams = Stream.query(Stream.stream_id != '').fetch()
        image_url = []

        for stream in streams:
            image_query = db.GqlQuery("SELECT *FROM Image WHERE ANCESTOR IS :1 ORDER BY upload_date DESC",
                                      db.Key.from_path('Stream', stream.stream_id))

            for image in image_query[0:stream.num_images]:
                d = dict()
                d["url"] = SERVICES_URL + "image?image_id=" + str(image.key())
                d["stream_id"] = stream.stream_id
                d["long"] = image.geo_loc.lon
                d["lat"] = image.geo_loc.lat
                image_url.append(d)

        mycmp = lambda a, b: ((target_long - a["long"]) * (target_long - a["long"]) +
                              (target_lat - a["lat"]) * (target_lat - a["lat"]) -
                              (target_long - b["long"]) * (target_long - b["long"]) -
                              (target_lat - b["lat"]) * (target_lat - b["lat"]))
        image_url.sort(mycmp)
        dict_passed = {'displayImages': image_url}
        json_obj = json.dumps(dict_passed, sort_keys=True, indent=4, separators=(',', ': '))
        self.response.write(json_obj)


class AndroidUploadImageHandler(webapp2.RequestHandler):
    def post(self):
        pictures = self.request.get_all('files')
        results = []
        print "Android_upload called"
        if len(pictures) > 0:
            stream_id = self.request.get('stream_id')
            print "stream name is ", stream_id
            str_lon = self.request.get('longitude')
            str_lat = self.request.get('latitude')
            print str_lon + " " + str_lat

            for image in pictures:
                if str_lon == "" or str_lat == "":
                    Stream.insert_with_lock(stream_id,image)
                else:
                    Stream.insert_with_lock(stream_id, image,True,float(str_lat), float(str_lon))

        #         results.append({'name': '', 'url': '', 'type': '', 'size': 0})
        #
        # s = json.dumps({'files': results}, separators=(',', ':'))
        # self.response.headers['Content-Type'] = 'application/json'
        # # print "duming material is ", s
        # return self.response.write(s)


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/login', LoginHandler),
    ('/manage', ManageHandler),
    ('/create', CreateHandler),
    ('/view_single', ViewStreamHandler),
    ('/view_user', ViewUserHandler),
    ('/view', ViewAllFriendHandler),
    ('/image', ViewImageHandler),
    ('/imageGeo', ViewImageObjectHandler),
    ('/search', SearchHandler),
    ('/trending', TrendingHandler),
    ('/error', ErrorHandler),
    ('/add_friend', AddFriendHandler),
    ('/create_a_new_stream', CreateANewStreamHandler),
    ('/delete_a_stream', DeleteStreamHandler),
    ('/upload_image', UploadImageHandler),
    ('/subscribe_a_stream', SubscribeStreamHandler),
    ('/unsubscribe_a_stream', UnsubscribeStreamHandler),
    ('/view_more', ViewMoreHandler),
    ('/report', ReportHandler),
    ('/geomap', GeoMapHandler),
    ('/auto_complete', AutoCompleteHandler),
    ('/android/view_all_streams', AndroidViewAllStreamsHandler),
    ('/android/view_single_stream', AndroidViewStreamHandler),
    ('/android/upload_image', AndroidUploadImageHandler),
    ('/android/view_nearby', AndroidViewNearby),
    ('/android/create_a_stream', AndroidCreateANewStreamHandler),
], debug=True)
