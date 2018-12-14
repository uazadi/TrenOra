import time, logging, re, requests, json
from telegram import (ReplyKeyboardMarkup,
                      ReplyKeyboardRemove)
from telegram.ext import (Updater,
                          CommandHandler,
                          MessageHandler,
                          Filters,
                          RegexHandler,
                          ConversationHandler)
from threading import Thread
from datetime import datetime, timedelta

from src.trenitalia import TrenitaliaBackend


# https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/conversationbot.py

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

DEPARTURE, ARRIVAL, TIME, NOTIFICATION = range(4)

# Dict where the keys are users id (telegram username)
# and the value is the list of Thread related to him.



class Users:
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if Users.__instance == None:
            Users()
        return Users.__instance


    def __init__(self):
        """ Virtually private constructor. """
        if Users.__instance != None:
            raise Exception("This class is a singleton class!")
        else:
            Users.__instance = self
            self.users = {}


class TrainRemainder (Thread):
    def __init__(self, bot, user):
        Thread.__init__(self)
        self.bot = bot
        self.user = user
        self.departing = ""
        self.arrival = ""
        self.train_time = ""
        self.train_code = ""
        self.notification_time = ""
        self.num_notification = ""

    def set_departing_station(self, departing):
        self.departing = departing

    def set_arrival_station(self, arrival):
        self.arrival = arrival

    def set_train_time(self, train_time):
        self.train_time = train_time.split("|")[0][:-1]
        self.train_code = train_time.split("|")[1][1:]

        print()

    def set_notification_time(self, not_time):
        self.notification_time = not_time

    def set_number_of_notification(self, number):
        self.num_notification = number

    def get_trains_availables(self):
        return search_train_tb(self.departing.split("|")[1],
                               self.arrival.split("|")[1], 10)

    def _get_notification_timestamp(self):
        timestamp = datetime.strptime(self.train_time, '%Y-%m-%d %H:%M:%S')

        match = re.match("((\d+)h){0,1}((\d+)m){0,1}((\d+)s){0,1}", self.notification_time)
        h = 0 if match.group(2) is None else int(match.group(2))
        m = 0 if match.group(4) is None else int(match.group(4))
        s = 0 if match.group(6) is None else int(match.group(6))
        timestamp = timestamp - timedelta(hours=h, minutes=m, seconds=s)

        #if 'h' in self.notification_time:
        #    match =
        #    timestamp = timestamp - timedelta(hours=int(match.group(1)))
        #if 'm' in self.notification_time:
        #    min = int(re.match(".*(\d{2})m.*", self.notification_time).group(1))
        #    timestamp = timestamp - timedelta(minutes=min)
        #if 's' in self.notification_time:
        #    sec = int(re.match(".*(\d{2})s.*", self.notification_time).group(1))
        #    timestamp = timestamp - timedelta(seconds=sec)

        return str(timestamp)

    def run(self):
        timestamp = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        notification_time = self._get_notification_timestamp()
        print(notification_time)

        while timestamp < notification_time:
            time.sleep(10)
            timestamp = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        self.bot.send_message(chat_id=self.user.message.chat_id, text="Time to take the train")

    def __str__(self):
        return self.user.message.chat.username + " " \
               + self.departing + " " \
               + self.arrival + " " \
               + self.train_time + " " \
               + self.train_code + " " \
               + self.notification_time + " " \
               + self.num_notification



#-----------------------------------TrainAPI-----------------------------------


def search_station(name_station):
    possible_stations = []
    if re.match("(\w|\s|\.|-|'|`)+", name_station):
        #--- versione con ViaggiaTreno
        #req = requests.get('http://www.viaggiatreno.it/viaggiatrenonew/'
        #                    'resteasy/viaggiatreno/autocompletaStazione/'
        #                    + name_station)
        # possible_stations = req.text.split("\n") if len(req.text) > 0 else []

        req = requests.get('https://www.lefrecce.it/msite/api/geolocations/locations?name='
                           + name_station)

        for station in json.loads(req.text):
            name = str(station["name"])
            possible_stations.append(name)

    return possible_stations

def search_station_tb(name_station):
    possible_stations = []
    tb = TrenitaliaBackend()
    output = tb.search_station(name=name_station,
                               only_italian=False)

    for station in output:
        possible_stations.append(str(station["name"]) + "|" + str(station["stationcode"]))
    return possible_stations

def search_train(departing, arrival):
    """
    :param departing: Code of the departing station
    :param arrival: Code of the arrival station
    :return: the list of trains available [["<departure time> | <train id>"], ....]
    """
    possible_times = []

    departing = departing.replace("S0", "")
    arrival = arrival.replace("S0", "")
    timestamp = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%dT%H:%M:%S')

    req = requests.get('http://www.viaggiatreno.it/viaggiatrenonew'
                       '/resteasy/viaggiatreno/soluzioniViaggioNew'
                       '/' + departing +
                       '/' + arrival +
                       '/' + timestamp)

    trains = []
    for travel in json.loads(req.text)["soluzioni"]:
        departure = str(travel["vehicles"][0]["orarioPartenza"]).replace("T", " ")
        id = str(travel["vehicles"][0]["numeroTreno"])
        trains.append([departure + " | " + id])

    return trains


def search_train_tb(departing, arrival, num_of_trains):
    tb = TrenitaliaBackend()

    trains_generator = tb.search_solution(departing,
                                    arrival,
                                    max_changes=0,
                                    limit=10,
                                    dep_date=datetime.now())
    trains = []
    for train in trains_generator:
        id = train["number"]
        dep_date = train["dep_date"]
        #arr_date = json.loads(train)["arr_date"]
        trains.append([dep_date + " | " + id])
    return trains


#-------------------------------------------------------------------------------


list_of_command = "/add_train  for add the allarm related to a train"
name = "TrenOra"

def start(bot, user):
    message = "Hi, my name is " + name + "!\n" \
              "My purpose is to make sure you don't lose you train!\n\n" \
              "Here the list of command that I understand:\n\n" + list_of_command
    bot.send_message(chat_id=user.message.chat_id, text=message)


def set_train(bot, update):
    user = update.message.from_user
    logger.info("Train selected depart at %s: %s", user.first_name, update.message.text)
    update.message.reply_text(
        ""
        'Send /cancel to stop talking to me.\n\n'
        'Which is your departing station?',
        reply_markup=ReplyKeyboardRemove())


    #reply_keyboard = [['Station1'], ['Station2'], ['Station3']]

    add_users(bot, update)

    #update.message.reply_text(
    #    ""
    #    'Send /cancel to stop talking to me.\n\n'
    #    'Which is your departing station?',
    #    reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

    return DEPARTURE


def add_users(bot, update):
    """
    Add a key value in the  Users Singleton class iff it hasn't already a value
    associated
    """
    id = update.message.chat.username
    train = TrainRemainder(bot, update)
    users = Users.getInstance().users
    if id in users:
        users[id].append(train)
    else:
        users[id] = [train]

    print(users)

def add_info(update, function):
    id = update.message.chat.username
    users = Users.getInstance().users
    function(users[id][-1])
    print(users[id][-1])


def departing_station(bot, update):

    user = update.message.from_user
    dep_station = update.message.text

    if not(re.fullmatch("((\w|\s|\.|-|'|`)+)\|([0-9])+", update.message.text)):
        possible_stations = search_station_tb(update.message.text)
        if len(possible_stations) <= 0:
            update.message.reply_text('Sorry, I couldn\'t find the station.\nCan you please try again?\n\n',
                                      reply_markup=ReplyKeyboardRemove())
            return DEPARTURE
        if len(possible_stations) > 1:
            reply_keyboard = [[station] for station in possible_stations]
            update.message.reply_text('Can you please select the correct station?\n\n',
                                      reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                       one_time_keyboard=True))

            return DEPARTURE
        if len(possible_stations) == 1:
            dep_station = possible_stations[0]


    logger.info("Departing station %s: %s", user.first_name, dep_station)
    update.message.reply_text('Great! Which is your arrival station? \n\n',
                              reply_markup=ReplyKeyboardRemove())
    add_info(update,
             lambda train: train.set_departing_station(dep_station))

    return ARRIVAL


def arrival_station(bot, update):
    user = update.message.from_user
    dep_station = update.message.text

    if not (re.fullmatch("((\w|\s|\.|-|'|`)+)\|([0-9])+", update.message.text)):
        possible_stations = search_station_tb(update.message.text)
        if len(possible_stations) <= 0:
            update.message.reply_text('Sorry, I couldn\'t find the station.\nCan you please try again?\n\n',
                                        reply_markup=ReplyKeyboardRemove())
            return ARRIVAL
        if len(possible_stations) > 1:
            reply_keyboard = [[station] for station in possible_stations]
            update.message.reply_text('Can you please select the correct station?\n\n',
                                        reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                                        one_time_keyboard=True))

            return ARRIVAL
        if len(possible_stations) == 1:
            dep_station = possible_stations[0]


    add_info(update,
             lambda train: train.set_arrival_station(dep_station))

    id = update.message.chat.username
    reply_keyboard = Users.getInstance().users[id][-1].get_trains_availables()



    logger.info("Arriving station %s: %s", user.first_name, dep_station)
    update.message.reply_text('Ok! Now, at which time you want to take the train \n\n',
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                                               one_time_keyboard=True))

    return TIME


def train(bot, update):
    user = update.message.from_user
    message = update.message.text

    logger.info("Train selected depart at %s: %s", user.first_name, message)
    update.message.reply_text('Fine! how much time before you want to be notified? \n'
                              'Please respect the following format <hours>h<minutes>m<seconds>s.\n\n'
                              'Examples: 30s, 1h2m, 1h5s, 1h20m3s\n',
                              reply_markup=ReplyKeyboardRemove())

    add_info(update,
             lambda train: train.set_train_time(message))

    return NOTIFICATION


def notification_time(bot, update):
    user = update.message.from_user
    logger.info("Notification time %s: %s", user.first_name, update.message.text)
    update.message.reply_text('Thank you! Now you don\'t need to think about it, '
                              'I will send you a message at the specified time!')

    add_info(update,
             lambda train: train.set_notification_time(update.message.text))

    id = update.message.chat.username
    Users.getInstance().users[id][-1].run()

    return ConversationHandler.END


def cancel(bot, update):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text('Bye! I hope we can talk again some day.',
                              reply_markup=ReplyKeyboardRemove())

    id = update.message.chat.username
    del Users.getInstance().users[id][-1]

    return ConversationHandler.END


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)

def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")


def main():
    # Create the EventHandler and pass it your bot's token.
    bot_id = ""
    with open('bot.txt') as f:
        bot_id = f.readline().split('=')[1]
    updater = Updater(bot_id)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler with the states GENDER, PHOTO, LOCATION and BIO
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_train', set_train)],

        states={
            DEPARTURE: [RegexHandler("(\w|\.|-|'|`)+", departing_station)],

            ARRIVAL: [RegexHandler("(\w|\.|-|'|`)+", arrival_station)],

            TIME: [RegexHandler('(.*)', train)],

            NOTIFICATION: [RegexHandler('((\d+)h){0,1}((\d+)m){0,1}((\d+)s){0,1}', notification_time)]
        },

        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(conv_handler)

    # log all errors
    dp.add_error_handler(error)

    start_handler = CommandHandler('start', start, pass_args=False)
    dp.add_handler(start_handler)
    unknown_handler = MessageHandler(Filters.command, unknown)
    dp.add_handler(unknown_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    print("TronOra is up...")
    main()
