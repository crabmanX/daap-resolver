#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Created by Christophe "Tito" De Wolf <tito@webtito.be> twitter.com/tito1337
# Licensed under GPLv3 (http://www.gnu.org/licenses/gpl)
######################################################################

import sys
import re
from struct import unpack, pack
import simplejson as json
from daap import DAAPClient
import logging
import difflib

###################################################################### config
DAAP_HOST = "10.0.73.1"
DAAP_PORT = "3689"

###################################################################### logger
# TODO : disable this when fully tested
logger = logging.getLogger('daap-resolver')
hdlr = logging.FileHandler('.daap-resolver.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)

logger.info('Started')


###################################################################### resolver
class DAAPresolver:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = DAAPClient()
        self.client.connect(host, port)
        logger.info("Connected to %s:%s"%(host,port))
        self.session = self.client.login()

        databases = self.session.databases()
        for d in databases:
            if str(d.id) == str(self.session.library().id):
                self.database = d

        self.tracks = self.database.tracks()
        logger.info("Got %s tracks"%len(self.tracks))

    def fulltext(self, search):
        founds = []
        logger.info('Searching %s in %d tracks'%(search, len(self.tracks)))
        seqMatch = difflib.SequenceMatcher(None, "foobar", search)
        for t in self.tracks:
            seqMatch.set_seq1(t.artist)
            score = seqMatch.quick_ratio()
            seqMatch.set_seq1(t.album)
            score = max( seqMatch.quick_ratio(),  score )
            seqMatch.set_seq1(t.name)
            score = max( seqMatch.quick_ratio(),  score )
            if score >= 0.3:
                found = dict()
                found["artist"] = t.artist
                found["track"]  = t.name
                found["album"]  = t.album
                if isinstance(t.time, int):
                    found["duration"] = int(t.time/1000)
                found["url"]    = 'http://%s:%s/databases/%d/items/%d.mp3?session-id=%s'%(self.host, self.port, self.database.id, t.id, self.session.sessionid)
                found["score"] = score
                #found["source"] = 'DAAP'
                founds.append(found)
        logger.info('Found %d tracks'%len(founds))
        return founds

    def artistandtrack(self, artist, track):
        founds = []
        logger.info('Searching %s - %s in %d tracks'%(artist, track, len(self.tracks)))
        seqMatchArtist = difflib.SequenceMatcher(None, "foobar", self.stripFeat(artist))
        seqMatchTrack = difflib.SequenceMatcher(None, "foobar", self.stripFeat(track))
        for t in self.tracks:
            seqMatchArtist.set_seq1(self.stripFeat(t.artist))
            seqMatchTrack.set_seq1(self.stripFeat(t.name))
            scoreArtist = seqMatchArtist.quick_ratio()
            scoreTrack = seqMatchTrack.quick_ratio()
            score = (scoreArtist + scoreTrack) /2
            if score >= 0.85:
                logger.debug("%s - %s : %s - %s : %f,%f,%s"%(artist, track, t.artist, t.name, scoreArtist, scoreTrack, score))
                found = dict()
                found["artist"] = t.artist
                found["track"]  = t.name
                found["album"]  = t.album
                if isinstance(t.time, int):
                    found["duration"] = int(t.time/1000)
                found["url"]    = 'http://%s:%s/databases/%d/items/%d.mp3?session-id=%s'%(self.host, self.port, self.database.id, t.id, self.session.sessionid)
                found["score"] = score
                #found["source"] = 'DAAP'
                founds.append(found)
        logger.info('Found %d tracks'%len(founds))
        return founds


    def stripFeat(self,  s):
        patterns = ['^(.*?)\(feat\..*?\).*?$',  '^(.*?)feat\..*?$']
        for pattern in patterns:
            reg = re.search(pattern,  s)
            if reg:
                s= reg.group(1)
        return s


###################################################################### functions
def print_json(o):
    s = json.dumps(o)
    sys.stdout.write(pack('!L', len(s)))
    sys.stdout.write(s)
    sys.stdout.flush()

###################################################################### init playdar
settings = dict()
settings["_msgtype"] = "settings"
settings["name"] = "DAAP Resolver"
settings["targettime"] = 400 # millseconds
settings["weight"] = 100 # mp3tunes results should be chosen just under the local collection
print_json( settings )


##################################################################### main
resolver = DAAPresolver(DAAP_HOST, DAAP_PORT)
while 1:
    length = sys.stdin.read(4)
    length = unpack('!L', length)[0]
    if not length:
        break
    if length > 4096 or length < 0:
        break
    if length > 0:
        msg = sys.stdin.read(length)
        request = json.loads(msg)
        logger.debug('Got request : %s'%request)
        if request['_msgtype'] == 'rq':
            if 'fulltext' in request: # User query
                tracks = resolver.fulltext(request['fulltext'])
            else:
                tracks = resolver.artistandtrack(request['artist'], request['track'])
                
            if len(tracks) > 0:
                response = { 'qid':request['qid'], 'results':tracks, '_msgtype':'results' }
                logger.debug('Sent response : %s'%response)
                print_json(response)
