__author__ = 'libochen'


from google.appengine.ext import ndb
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext import db
import threading
from datetime import datetime
from random import randrange


class User(ndb.Model):
    user_id = ndb.StringProperty()
    nick_name = ndb.StringProperty()
    friends = ndb.StringProperty(repeated=True)
    streams = ndb.StringProperty(repeated=True)
    photo = ndb.StringProperty()
    description = ndb.StringProperty()


class ChatRoom(ndb.Model):
    members = ndb.StringProperty(repeated=True)
    normalized_longitude = ndb.IntegerProperty()
    normalized_latitude = ndb.IntegerProperty()
    messages = ndb.StringProperty(repeated=True)


class Image(db.Model):
    owner_id = db.StringProperty()
    image = db.BlobProperty()
    stream_id = db.StringProperty()
    upload_date = db.DateTimeProperty(auto_now_add=True)
    geo_loc = db.GeoPtProperty()


class Stream(ndb.Model):
    owner = ndb.StringProperty()       #used to solve can't see others problem
    stream_id = ndb.StringProperty()
    user_id = ndb.StringProperty()
    last_add = ndb.StringProperty()
    information = ndb.StringProperty()
    views = ndb.IntegerProperty()
    num_images = ndb.IntegerProperty()
    cover_url = ndb.StringProperty()
    subscribers = ndb.StringProperty(repeated=True)
    tags = ndb.StringProperty()
    view_queue = ndb.DateTimeProperty(repeated=True)
    mylock = threading.Lock()
    geo_loc = ndb.GeoPtProperty()
    count = {}
    # def initialize(self, count):
    #     self.count = count

    @classmethod
    def query_stream(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key).order(-cls.last_add)

    @classmethod
    def reset_image_num(cls, stream_id):
        cls.count[stream_id] = 0

    @classmethod
    def insert_with_lock(cls, stream_id, image,random=True,lat=None,lon=None):
        cls.mylock.acquire()
        print "*******" + str(cls.count) + "*******";
        stream_query = Stream.query(Stream.stream_id == stream_id)
        stream = stream_query.fetch()[0]
        # stream.num_images += 1
        # print "current image numbers: " + str(stream.num_images)
        user_image = Image(parent=db.Key.from_path('Stream', stream_id))
        # stream.image_list.append('0')
        image = images.resize(image, 320, 400)
        user_image.image = db.Blob(image)
        # get random geoPoint
        if random:
            user_image.geo_loc = db.GeoPt(randrange(-10,10),randrange(-10,10))
        else:
            user_image.geo_loc = db.GeoPt(lat,lon)
        stream.last_add = str(datetime.now())
        user_image.put()

        print "*******************", cls.count
        print "******************* stream_id is", stream_id

        if stream_id not in cls.count:
            cls.count[stream_id] = 0

        cls.count[stream_id] += 1
        print "entercount numebr is ", cls.count[stream_id]
        stream.num_images = cls.count[stream_id]
        stream.put()
        cls.mylock.release()


class StreamInfo(ndb.Model):
    created = ndb.KeyProperty(repeated=True)
    subscribed = ndb.KeyProperty(repeated=True)

    @classmethod
    def query_stream(cls, ancestor_key):
        return cls.query(ancestor=ancestor_key)


class ShowStream:
    def __init__(self, image_url, views, stream_id):
        self.url = image_url
        self.views = views
        self.stream_id = stream_id

