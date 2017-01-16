import re
import sys
import twitter
import json
import configparser
import xmltodict
import ns_api
import datetime
import sched, time
import secret
from random import randint
from datetime import datetime as dt

from utilkit import datetimeutil

'''
My little TODO list
- add way of updating and storing userID
- request max 1 hour station list
'''

__domain__ = ''	# Domain name that will be used in the link thats in the tweet
__dict__ = timeDict = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "a": 10, "b": 11,
                       "c": 12, "d": 13, "e": 14, "f": 15, "g": 16, "h": 17, "i": 18, "j": 19, "k": 20, "l": 21,
                       "m": 22, "n": 23, "o": 24, "p": 25, "q": 26, "r": 27, "s": 28, "t": 29, "u": 30, "v": 31,
                       "w": 32, "x": 33, "y": 34, "z": 35, "A": 36, "B": 37, "C": 38, "D": 39, "E": 40, "F": 41,
                       "G": 42, "H": 43, "I": 44, "J": 45, "K": 46, "L": 47, "M": 48, "N": 49, "O": 50, "P": 51,
                       "Q": 52, "R": 53, "S": 54, "T": 55, "U": 56, "V": 57, "W": 58, "X": 59}

# general
TWITTER_CHAR_LIMIT = 140
POST_LINK = True
POLL_TIME = 60  # get tweets once a minute
STATION_UPDATE_TIME = 1440  # update once a day
TIME_FIRST_TRAIN_SECONDS = 180  # min time for next train is 3 min

# file names
FILE_NAME_SETTINGS = 'settings.ini'

# settings.ini constants
SETTINGS_DEFAULT = 'DEFAULT'
SETTINGS_SETTINGS = 'SETTINGS'
SETTINGS_MOST_RECENT_TWEET_ID = 'most_recent_tweet'
SETTINGS_MOST_RECENT_TWEET_ID_DEFAULT = '-1'
SETTINGS_IS_INIT = 'is_init'
SETTINGS_IS_INIT_DEFAULT = 'True'
SETTINGS_LAST_PROCESSED_TWEET_ID = 'last_processed_tweet_id'
SETTINGS_LAST_PROCESSED_TWEET_ID_DEFAULT = '-1'

# json constants tweet 'object'
JSON_TWEET_CREATED_AT = 'created_at'
JSON_TWEET_HASHTAGS = 'hashtags'
JSON_TWEET_ID = 'id'
JSON_TWEET_ID_STR = 'id_str'
JSON_TWEET_LANG = 'lang'
JSON_TWEET_SOURCE = 'source'
JSON_TWEET_TEXT = 'text'
JSON_TWEET_URLS = 'urls'
JSON_TWEET_USER = 'user'
JSON_TWEET_USER_MENTIONS = 'user_mentions'
JSON_TWEET_USER_ID_REPLY = 'in_reply_to_user_id'

# json constants user 'object' in tweet
JSON_USER_CREATED_AT = 'created_at'
JSON_USER_DEFAULT_PROFILE = 'default_profile'
JSON_USER_DESCRIPTION = 'description'
JSON_USER_ID = 'id'
JSON_USER_LANG = 'lang'
JSON_USER_LOCATION = 'location'
JSON_USER_NAME = 'name'
JSON_USER_PROFILE_BACKGROUND_COLOR = 'profile_background_color'
JSON_USER_PROFILE_IMAGE_URL = 'profile_image_url'
JSON_USER_PROFILE_LINK_COLOR = 'profile_link_color'
JSON_USER_PROFILE_SIDEBAR_FILL_COLOR = 'profile_sidebar_fill_color'
JSON_USER_PROFILE_TEXT_COLOR = 'profile_text_color'
JSON_USER_SCREEN_NAME = 'screen_name'
JSON_USER_STATUSES_COUNT = 'statuses_count'

# ns-api
NS_STATION_NAME_SHORT = 'short'
NS_STATION_NAME_MIDDLE = 'middle'
NS_STATION_NAME_LONG = 'long'
NS_INDEX = 'index'
NS_STATION = 'station'

'''
The idea of TwitterBot is to keep all data contained in the class, and not give data with the class.
Create the class and tell it what to do with its data, no methods to do something with extra data from outside
'''

'''
Method to convert XML to Json so that everything can be parsed with Json
'''

# scheduler to schedule running the bot every n seconds
s = sched.scheduler(time.time, time.sleep)


def xml_to_json(json_srt) -> json.dumps:
    str(json_srt)
    string = xmltodict.parse(json_srt)
    return json.dumps(string)


# TODO: check if variables contain the correct stuff
class SettingsParser:
    def __init__(self):
        self.cp = configparser.ConfigParser()
        self.init_settings(False)  # on default doesn't overwrite settings file

    '''
    :param ignore_existing_file: if FILE_NAME_SETTINGS already exists will overwrite FILE_NAME_SETTINGS with default values
    :returns True if file is edited
    '''

    def init_settings(self, ignore_existing_file: bool = False) -> bool:
        self.cp.read(FILE_NAME_SETTINGS)
        # check if settings file already contains correct content
        if SETTINGS_DEFAULT in self.cp and SETTINGS_SETTINGS in self.cp and not ignore_existing_file:
            return False
        # reset settings file/create new settings file
        self.cp[SETTINGS_DEFAULT] = {SETTINGS_MOST_RECENT_TWEET_ID: SETTINGS_MOST_RECENT_TWEET_ID_DEFAULT,
                                     SETTINGS_LAST_PROCESSED_TWEET_ID: SETTINGS_LAST_PROCESSED_TWEET_ID_DEFAULT,
                                     SETTINGS_IS_INIT: SETTINGS_IS_INIT_DEFAULT}
        self.cp[SETTINGS_SETTINGS] = {}
        with open(FILE_NAME_SETTINGS, 'w') as configfile:
            self.cp.write(configfile)
        return True

    def get_recent_tweet_id(self) -> str:
        if SETTINGS_SETTINGS in self.cp:
            settings = self.cp[SETTINGS_SETTINGS]
        elif SETTINGS_DEFAULT in self.cp:
            settings = self.cp[SETTINGS_DEFAULT]
        else:
            print('settings are not initialized')
            self.init_settings(True)
            return self.get_recent_tweet_id()  # call self after init settings
        return settings[SETTINGS_MOST_RECENT_TWEET_ID]

    def get_last_processed_tweet_id(self) -> str:
        if SETTINGS_SETTINGS in self.cp:
            settings = self.cp[SETTINGS_SETTINGS]
        elif SETTINGS_DEFAULT in self.cp:
            settings = self.cp[SETTINGS_DEFAULT]
        else:
            print('settings are not initialized')
            self.init_settings(True)
            return self.get_last_processed_tweet_id()  # call self after init settings
        return settings[SETTINGS_LAST_PROCESSED_TWEET_ID]


class TwitterBot:
    def __init__(self):
        self.departure_dict = {}
        self.settings = SettingsParser()
        self.settings.init_settings(False)  # init settings
        # init api
        self.api = twitter.Api(consumer_key=secret.__consumer_key__, consumer_secret=secret.__consumer_secret__,
                               access_token_key=secret.__access_token_key__,
                               access_token_secret=secret.__access_token_secret__, sleep_on_rate_limit=True)
        # get id's from settings file, either -1 or a proper id
        self.most_recent_tweet_id = self.settings.get_recent_tweet_id()
        self.last_processed_tweet_id = self.settings.get_last_processed_tweet_id()
        self.tweets_list = ''
        # set up ns api
        self.ns_api = ns_api.NSAPI(username=secret.USERNAME, apikey=secret.PASSWORD)
        self.stations = []  # get all station names
        self.get_all_stations()
        if not self.verify_oauth:
            print("Something went wrong with the twitter authentication\nExiting...")
            return

    def __str__(self) -> str:
        return str(self.api.VerifyCredentials())

    def verify_oauth(self) -> bool:
        try:
            self.api.VerifyCredentials()[JSON_USER_CREATED_AT]  # fails if not authenticated
            return True
        except:
            return False

    def get_all_stations(self):
        self.stations = self.ns_api.get_stations()

    def get_all_tweets_from(self) -> list:
        self.get_user_ids()
        if self.last_processed_tweet_id == '-1':  # first run
            self.tweets_list = self.api.GetMentions()
        else:
            self.tweets_list = self.api.GetMentions(since_id=self.last_processed_tweet_id)  # self.tweets_list[0]

        # filter out own tweets
        tweets_temp = []
        for i in range(len(self.tweets_list)):
            json_tweet = json.loads(str(self.tweets_list[i]))
            if str(json_tweet[JSON_TWEET_USER][JSON_USER_ID]) != secret.__userID__:  # skip own tweets
                tweets_temp.append(self.tweets_list[i])  # store in new list
        self.tweets_list = tweets_temp

        # store most recent id of tweet for later reference
        if len(self.tweets_list) > 0:
            json_tweet_most_recent = json.loads(str(self.tweets_list[0]))  # first tweet in the list is most recent
            self.most_recent_tweet_id = json_tweet_most_recent[JSON_TWEET_ID]
            self.store_user_id(most_recent=self.most_recent_tweet_id)  # store most recent tweet
        print("tweets:", self.tweets_list)  # print list of tweets, remove later
        return self.tweets_list

    '''
    Method that goes through all the new tweets and gets an answer and tweet back
    '''

    def process_tweets(self):
        # start from the back because that's the oldest tweet that isn't processed yet
        for tweet in reversed(self.tweets_list):
            print("tweet to process:", tweet)
            # skip own tweets just to be sure
            tweet = json.loads(str(tweet))
            if str(tweet[JSON_TWEET_USER][JSON_USER_ID]) != secret.__userID__:
                tweet_content = self.get_ns_route(tweet[JSON_TWEET_TEXT],
                                                  user=tweet[JSON_TWEET_USER][JSON_USER_SCREEN_NAME])
                tweet_id = tweet[JSON_TWEET_ID]
                # tweet the response
                self.tweet(data=tweet_content)
                self.store_user_id(last_processed=tweet_id)
                # store most recent tweet that was processed
                # if len(self.tweets_list) > 0:
                #     json_tweet_most_recent = json.loads(str(self.tweets_list[0]))   # first tweet in the list is most recent
                #     self.last_processed_tweet_id = json_tweet_most_recent[JSON_TWEET_ID]

    '''
    Method that tweets at a user with some data
    '''

    def tweet(self, data: str = '') -> json.loads:
        if data == '':
            return False
        response = self.api.PostUpdate(status=data)
        response = json.loads(str(response))
        print("response:", response)
        return response[JSON_TWEET_ID_STR]

    def get_ns_route(self, text: str, user: str) -> str:
        text = str.lower(text)
        # brute force for now
        # TODO: make smarter, 'i want to go to B, departing from A' will result in from_station = B and to_station = A #not_correct
        from_station = ""
        to_station = ""
        via_station = ""
        stations_tuples = []
        for station in self.stations:
            # check if station is in string. find returns -1 if substring is not found
            small_index = str.find(text, " " + str.lower(station.names[NS_STATION_NAME_SHORT]))
            middle_index = str.find(text, " " + str.lower(station.names[NS_STATION_NAME_MIDDLE]))
            long_index = str.find(text, " " + str.lower(station.names[NS_STATION_NAME_LONG]))
            if long_index != -1:
                stations_tuples.append({NS_INDEX: long_index, NS_STATION: station.names[NS_STATION_NAME_LONG]})
            elif middle_index != -1:
                stations_tuples.append({NS_INDEX: middle_index, NS_STATION: station.names[NS_STATION_NAME_MIDDLE]})
            elif small_index != -1:
                stations_tuples.append({NS_INDEX: small_index, NS_STATION: station.names[NS_STATION_NAME_SHORT]})
            else:
                for synonym in station.synonyms:
                    syn_index = str.find(text, " " + str.lower(synonym))
                    if syn_index != -1:
                        # found synonym
                        stations_tuples.append({NS_INDEX: syn_index, NS_STATION: synonym})
                        break

        if len(stations_tuples) < 2:
            return self.cant_find_route_return()  # need at least two stations
        # remove false positives
        # n^2 running time to filter out wrong stations, jee. good that there are only 140 characters
        #   and (assumption) not that many stations
        # see if station_tuple_small is subset of station_tuple_big
        # subset in the sens that the station name is a subset and that the position of the characters is a subset
        # if a station is names twice, will remove both instances and probably give a cant find route back,
        #   if we want to keep both change the <= part to only <
        temp_list = []
        for station_tuple_small in stations_tuples:
            for station_tuple_big in stations_tuples:
                # skip if is the same station in the list
                if station_tuple_small != station_tuple_big:
                    # is not small string is subset of bigger string or is not in same location as bigger string
                    if str.find(str.lower(station_tuple_big[NS_STATION]),
                                str.lower(station_tuple_small[NS_STATION])) != -1 \
                            and (station_tuple_big[NS_INDEX] <= station_tuple_small[NS_INDEX] <= station_tuple_big[
                                NS_INDEX] + len(station_tuple_big[NS_STATION])):
                        station_tuple_small[NS_INDEX] = -1  # later delete all with index -1
                        break
            if station_tuple_small[NS_INDEX] != -1:
                temp_list.append(station_tuple_small)
        stations_tuples = temp_list

        if len(stations_tuples) < 2:
            return self.cant_find_route_return()  # need at least two stations
        smallest = 2 * TWITTER_CHAR_LIMIT  # need to find something that is smallest, start with big number
        middle = -1
        biggest = -1  # need to find something that is biggest, start with small number
        for i in range(2):  # run twice, once doesn't work
            for station_tuple in stations_tuples:
                updated = False
                if station_tuple[NS_INDEX] <= smallest:
                    smallest = station_tuple[NS_INDEX]
                    updated = True
                if station_tuple[NS_INDEX] >= biggest:
                    biggest = station_tuple[NS_INDEX]
                    updated = True
                if not updated:
                    middle = station_tuple[NS_INDEX]
        # get the first and last stations that are mentioned in the tweet
        for station_tuple in stations_tuples:
            if station_tuple[NS_INDEX] == smallest:
                from_station = station_tuple[NS_STATION]
            elif station_tuple[NS_INDEX] == biggest:
                to_station = station_tuple[NS_STATION]
            elif station_tuple[NS_INDEX] == middle:
                via_station = station_tuple[NS_STATION]
            if from_station != "" and to_station != "" and via_station != "":
                break
        if from_station == "" or to_station == "":
            return self.cant_find_route_return()

        timezone_string = '+0100'
        if datetimeutil.is_dst('Europe/Amsterdam'):
            timezone_string = '+0200'
        pref_time_str = self.get_time_from_string(text)
        if pref_time_str is None:
            pref_time_str = self.convert_timezone(hour=datetime.datetime.utcnow().strftime("%H"),
                                                  minute=datetime.datetime.utcnow().strftime("%M"),
                                                  offset=timezone_string)
        # get datetime object
        pref_time_str = time.strftime("%d-%m-%Y") + ' ' + pref_time_str
        pref_time_datetime = datetimeutil.load_datetime(pref_time_str + timezone_string, "%d-%m-%Y %H:%M%z")
        while (pref_time_datetime.replace(tzinfo=None) - datetime.datetime.utcnow()).total_seconds() < 10:
            pref_time_datetime += datetime.timedelta(days=1)  # time is in the future, add a day
        # ns_api.py asks for &via= in url, but should be &viaStation=
        trips = self.ns_get_route(from_station=from_station, via_station="&viaStation=" + via_station, to_station=to_station, timestamp=pref_time_str)
        amount = len(trips)
        if amount < 1:
            return self.cant_find_route_return()

        trip_parts = None
        for trip in trips:
            if (trip.departure_time_actual - pref_time_datetime).total_seconds() >= TIME_FIRST_TRAIN_SECONDS:
                # first route that leaves at least TIME_FIRST_TRAIN_SECONDS seconds after now
                trip_parts = trip.trip_parts
                break
        if trip_parts is None:
            trip_parts = trips[1].trip_parts  # no route was found so guess this one

        if len(trip_parts) > 0:
            if len(trip_parts[0].stops) > 0:
                stop_start = trip_parts[0].stops[0]
                stop_end = trip_parts[0].stops[len(trip_parts[0].stops) - 1]
                url = self.make_url_to_website(station_from=from_station, station_via=via_station
                                               , station_to=to_station, time_departure=pref_time_datetime)
                if url == "error":
                    return self.cant_find_route_return()
                time_departure = stop_start.time.strftime("%H") + ":" + stop_start.time.strftime("%M")
                return self.can_find_route_return(station_from=stop_start.name, station_to=stop_end.name,
                                                  departure_time=time_departure, departure_track=stop_start.platform,
                                                  user=user, url=url, recursive=True)
        return self.cant_find_route_return()

    '''
    method that calls the ns_api with the stations and returns a Trip object. If one of the stations is badly specified will return None
    timestamp can be "" because api will ignore faulty timestamps, so default is departure now
    '''

    def ns_get_route(self, from_station: str = None, via_station: str = None, to_station: str = None, timestamp: str = None) -> list:
        if from_station is None or to_station is None:
            return None
        if timestamp is None:
            timestamp = datetime.datetime.utcnow().strftime("%H:%M")
        return self.ns_api.get_trips(timestamp=timestamp, start=from_station, via=via_station, destination=to_station,
                                     next_advices=1, prev_advices=1)

    '''
    Method to store the user_id to disk
    '''

    def store_user_id(self, most_recent: int = -1, last_processed: int = -1):
        # if most_recent == -1:
        #     return
        self.settings.init_settings(False)
        config = configparser.ConfigParser()
        config.read(FILE_NAME_SETTINGS)
        if most_recent != -1:
            config[SETTINGS_SETTINGS][SETTINGS_MOST_RECENT_TWEET_ID] = str(most_recent)
        if last_processed != -1:
            config[SETTINGS_SETTINGS][SETTINGS_LAST_PROCESSED_TWEET_ID] = str(last_processed)
        with open(FILE_NAME_SETTINGS, 'w') as configfile:
            config.write(configfile)

    '''
    Method to load the user_id from disk
    '''

    def get_user_ids(self):
        self.settings.init_settings(False)
        config = configparser.ConfigParser()
        config.read(FILE_NAME_SETTINGS)
        self.last_processed_tweet_id = config[SETTINGS_SETTINGS][SETTINGS_LAST_PROCESSED_TWEET_ID]
        self.most_recent_tweet_id = config[SETTINGS_SETTINGS][SETTINGS_MOST_RECENT_TWEET_ID]

    def get_departure_track_dict(self, station: str):
        departures = self.ns_api.get_departures(station=station)
        self.departure_dict = {}
        for departure in departures:
            self.departure_dict[departure.trip_number] = departure.departure_platform['#text']

    def make_url_to_website(self, station_from: str, station_via: str, station_to: str, time_departure: datetime.datetime) -> str:
        if not POST_LINK:
            return ""
        if not (type(station_from) is str and type(station_to) is str and type(time_departure) is datetime.datetime):
            return "error"
        if not type(station_via) is str or station_via is None:
            station_via = ""
        # add timezone to hour
        hour = self.convert_to_base60(time_departure.strftime("%H"))
        minute = self.convert_to_base60(time_departure.strftime("%M"))
        from_station_code = ""
        to_station_code = ""
        via_station_code = ""
        station_from = str.lower(station_from)
        station_to = str.lower(station_to)
        station_via = str.lower(station_via)
        # map station name to station
        for station in self.stations:
            if from_station_code != "" and to_station_code != "" and via_station_code != "":
                break
            if station_from == str.lower(station.names[NS_STATION_NAME_SHORT]):
                from_station_code = station.code
            elif station_to == str.lower(station.names[NS_STATION_NAME_SHORT]):
                to_station_code = station.code
            elif station_via == str.lower(station.names[NS_STATION_NAME_SHORT]):
                via_station_code = station.code
            if station_from == str.lower(station.names[NS_STATION_NAME_MIDDLE]):
                from_station_code = station.code
            elif station_to == str.lower(station.names[NS_STATION_NAME_MIDDLE]):
                to_station_code = station.code
            elif station_via == str.lower(station.names[NS_STATION_NAME_MIDDLE]):
                via_station_code = station.code
            if station_from == str.lower(station.names[NS_STATION_NAME_LONG]):
                from_station_code = station.code
            elif station_to == str.lower(station.names[NS_STATION_NAME_LONG]):
                to_station_code = station.code
            elif station_via == str.lower(station.names[NS_STATION_NAME_LONG]):
                via_station_code = station.code
            for syn in station.synonyms:
                syn = str.lower(syn)
                if station_from == syn:
                    from_station_code = station.code
                elif station_to == syn:
                    to_station_code = station.code
                elif station_via == syn:
                    via_station_code = station.code
        if from_station_code == "" or to_station_code == "":
            return "error"
        if via_station_code != "":
            return __domain__ + "/?s=" + from_station_code + "&v=" + via_station_code + "&d=" + to_station_code + "&t=" + hour + minute
        return __domain__ + "/?s=" + from_station_code + "&d=" + to_station_code + "&t=" + hour + minute

    def convert_to_base60(self, time_unit: "str or int [0:60)") -> str:
        return list(__dict__.keys())[list(__dict__.values()).index(int(time_unit))]

    '''
    Method that returns a random answer selected from a list, this to make it look better
    '''

    def cant_find_route_return(self) -> str:
        return {
            0: "Not again, sorry, but I couldn't find a route :(",
            1: "I'm sorry, I couldn't find a route",
            2: "Failed to find a route",
            3: "Nobody is perfect\n (I failed to find a route for you)",
            4: "Sorry, I failed to find a route",
            5: "No routes found",
            6: "Sorry, couldn't find a route, have you tried our website? " + __domain__,
        }.get(randint(0, 6), "I'm sorry, I couldn't find a route")

    '''
    Method that returns a random answer selected from a list, this to make it look better
     '''

    def can_find_route_return(self, station_from: str, station_to: str, departure_time: "str pref in HH:MM format",
                              departure_track: "pref str but int also possible", user: str, url: str,
                              recursive) -> str:
        if station_from is None or station_to is None or departure_time is None or departure_track is None:
            return self.cant_find_route_return()
        # context = "@" + user + " Train from " + station_from + " to " + station_to + " from track " + departure_track + " at " + departure_time
        context = {
            0: "Train from " + station_from + " to " + station_to + " from track " + departure_track + " at " + departure_time,
            1: "A train from " + station_from + " to " + station_to + " at track " + departure_track + " departs at " + departure_time,
            2: "From " + station_from + " departs a train from " + departure_track + " at " + departure_time + " towards " + station_to,
        }.get(randint(0, 2),
              "Train from " + station_from + " to " + station_to + " from track " + departure_track + " at " + departure_time)
        context = "@" + user + " " + context
        new_url = "\n" + url + " for more details"
        if POST_LINK and len(context) + len(new_url) <= 140:
            return context + new_url
        elif len(context) + len(new_url) > 140 and recursive:
            return self.can_find_route_return(station_from=self.get_station_short_name(station_name=station_from),
                                              station_to=self.get_station_short_name(station_name=station_to),
                                              departure_time=departure_time,
                                              departure_track=departure_track,
                                              user=user,
                                              url=url,
                                              recursive=False)  # prevent infinite loop
        elif len(context) <= 140:
            return context
        elif recursive:
            return self.can_find_route_return(station_from=self.get_station_short_name(station_name=station_from),
                                              station_to=self.get_station_short_name(station_name=station_to),
                                              departure_time=departure_time,
                                              departure_track=departure_track,
                                              user=user,
                                              url=url,
                                              recursive=False)  # prevent infinite loop
        return self.cant_find_route_return()

    def get_station_short_name(self, station_name: str):
        for station in self.stations:
            if str.lower(station_name) == str.lower(station.names[NS_STATION_NAME_SHORT]) or str.lower(
                    station_name) == str.lower(station.names[NS_STATION_NAME_MIDDLE]) or str.lower(
                station_name) == str.lower(station.names[NS_STATION_NAME_LONG]):
                return station.names[NS_STATION_NAME_SHORT]
            for synonym in station.synonyms:
                if str.lower(station_name) == str.lower(synonym):
                    return station.names[NS_STATION_NAME_SHORT]
        return station_name

    '''
    Method that adds/subtracts the timezone offset from the hours and minutes. 12:30+0130 becomes 14:00
    Makes sure that the answer is between 0 and 24 for hours and between 0 and 60 for minutes
    '''

    def convert_timezone(self, hour: "pref int, str also possible", minute: "pref int, str also possible",
                         offset: "str in {+,-}xxxx format") -> str:  # return str in format HH:MM
        if type(hour) is not int and type(hour) is str:
            hour = int(hour)
        if type(minute) is not int and type(minute) is str:
            minute = int(minute)
        if type(offset) is not str:
            return str(hour) + ":" + str(minute)
        # data is prob correct
        if offset[:1] == '+':
            hour_new = hour + int(offset[1:3])
            minute_new = minute + int(offset[3:])
        elif offset[:1] == '-':
            hour_new = hour - int(offset[1:3])
            minute_new = minute - int(offset[3:])
        else:
            if hour < 10:
                hour = '0' + str(hour)
            if minute < 10:
                minute = '0' + str(minute)
            return str(hour) + ":" + str(minute)
        if 0 <= minute_new < 10:
            minute_new = '0' + str(minute_new)
        elif minute_new < 0:
            minute_new %= 60
        elif minute_new >= 60:
            # add one to hour
            minute_new %= 60
            hour_new += 1
        if 0 <= hour_new < 10:
            hour_new = '0' + str(hour_new)
        elif hour_new >= 24 or hour_new < 0:  # python mod always returns positive outcome for mod
            hour_new %= 24
        return str(hour_new) + ":" + str(minute_new)

    '''
    Method to get a HH:MM formatted time from a string if present
    Returns None if time is not found
    '''

    def get_time_from_string(self, text: str) -> str:
        m = re.search("[0-9]{2}:[0-9]{2}", text)
        if m:
            time = m.group(0)
            if self.check_valid_time(time):
                return time
        return None

    def check_valid_time(self, time: "str in HH:MM format") -> bool:
        hour = int(time[:2])
        minute = int(time[3:])
        return not (hour >= 24 or hour < 0 or minute >= 60 or minute < 0)

def main():
    # init api
    bot = TwitterBot()
    # run once, start_polling() runs first time after n seconds
    bot.get_all_tweets_from()
    bot.process_tweets()
    start_polling(polling_delay=POLL_TIME, bot=bot)


def poll(sc: sched.scheduler, bot: TwitterBot, prev_update_time: int = 0):
    if bot is not None:
        if time.time() - prev_update_time > STATION_UPDATE_TIME:  # check if stations need to be updated
            update_stations(bot)
            prev_update_time = time.time()
        print("Polling for tweets")
        bot.get_all_tweets_from()
        bot.process_tweets()
    s.enter(POLL_TIME, 1, poll, (sc, bot, prev_update_time))


def update_stations(bot: TwitterBot):
    if bot is not None:
        print("Updating stations list")
        bot.get_all_stations()


def start_polling(polling_delay: int, bot: TwitterBot):
    s.enter(polling_delay, 1, poll, (s, bot, time.time()))
    s.run()


def test():
    bot = TwitterBot()
    print(bot.get_time_from_string("dfghfdhgd11:23adgfsfhfgh"))
    # cp = SettingsParser()
    # cp.init_settings(False)
    # print(cp.get_recent_tweet_id())
    # print(cp.get_last_processed_tweet_id())


if __name__ == '__main__':
    main()
    # test()
