#!/usr/bin/env python
# NFC KICKERBOT
# See https://github.com/bartmuskala/NFC-kickerbot for documentation
#
# Import required packages
import threading
import requests
import time
from datetime import datetime, timedelta
from slackeventsapi import SlackEventAdapter
import mysql.connector
import calendar
from smartcard.scard import *
import smartcard.util
from smartcard.util import toHexString
from smartcard.CardMonitoring import CardMonitor, CardObserver
import matplotlib.pyplot as plt
from io import BytesIO
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
import os

# Add ATR code line for the NFC reader to work with the pyscard library - don't adjust, should work like this
srTreeATR = \
    [0x3B, 0x77, 0x94, 0x00, 0x00, 0x82, 0x30, 0x00, 0x13, 0x6C, 0x9F, 0x22]
srTreeMask = \
    [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

# Define the NFC reader settings
NFC_DEVICE_PATH = 0

# Define Slack settings
CHANNEL_NAME = '#kickerstats'
SLACK_API_TOKEN_APP = os.environ.get('SLACK_API_TOKEN_APP')
SIGNING_SECRET = os.environ.get('SIGNING_SECRET')

# Customizable colors
COLOR_GAMES_WON = '#53b4c5'  # Games Won color (Blue)
COLOR_GAMES_PLAYED = '#b2eaf2'  # Games Played color (Green)
COLOR_WIN_RATIO = '#e65000'  # Win Ratio color (Red)

# Define MySQL settings for localhost
MYSQL_HOST = '127.0.0.1'
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
MYSQL_DATABASE = 'nfckickerbot'

# Global variables
players = set()
winner_ids = set()
winners = set()
game_in_progress = False
slack_client = WebClient(token=SLACK_API_TOKEN_APP)
slack_events_adapter = SlackEventAdapter(SIGNING_SECRET, endpoint="/slack/events")
db_connection = None

# Initialize MySQL database (only first time important for setting tables)
def initialize_database():
    global db_connection
    db_connection = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    cursor = db_connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INT AUTO_INCREMENT PRIMARY KEY,
            card_id VARCHAR(255) NOT NULL,
            username VARCHAR(255) NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            player1 VARCHAR(255) NOT NULL,
            player2 VARCHAR(255) NOT NULL,
            player3 VARCHAR(255) NOT NULL,
            player4 VARCHAR(255) NOT NULL,
            winner1 VARCHAR(255) NOT NULL,
            winner2 VARCHAR(255) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db_connection.commit()

# Used to send slack messages
def send_slack_message(message):
    try:
        response = slack_client.chat_postMessage(
            channel=CHANNEL_NAME,
            text=message
        )
        if not response["ok"]:
            print(f"Error sending message to Slack: {response['error']}")
    except SlackApiError as e:
        print(f"Slack API Error: {e.response['error']}")

# Retrieve the card_id from a message
import re

def extract_card_id(message):
    # Define a pattern to match "Ik: <card_id>"
    pattern = r'(?:ID|ADD ID): (.+)'

    # Use re.search to find the match
    match = re.search(pattern, message)

    # Check if there is a match
    if match:
        # Extract the card_id group
        card_id = match.group(1)
        return card_id
    else:
        # Return None if no match is found
        return None

# When a message is captured, it will add the user if it contains 'ID'
def on_slack_message(channel, user, user_id, message):
    global players, game_in_progress
    print(f'on slack message aangeroepen / message = "' + message + '" en channel = "'+ channel +'" en user = "'+ user +'"')
    if message.startswith('ID'):
        card_id = extract_card_id(message)
        print(f'New player identified: {user}')
        status = "new"
        # voeg user toe aan database
        add_database_user(card_id, user, user_id, status)
    elif message.startswith('ADD ID'):
        card_id = extract_card_id(message)
        print(f'Player card to be updated for: {user}')
        status = "update"
        # voeg user toe aan database
        add_database_user(card_id, user, user_id, status)
        
# Read the NFC card and do 1 of multiple options (add user, start game, finish game)
def on_card_read(tag):
    global players, winners, game_in_progress, card_id, username, losers
    # card_id = tag.identifier.hex().upper() ## This works for NFCPY (not for PYNFC :)
    card_id = tag
    print("card_id found: " + card_id)
   # Initialize cursor outside of try block
    cursor = db_connection.cursor(dictionary=True)

    try:
        # Fetch user information from the database based on the card_id
        cursor.execute('SELECT * FROM players WHERE card_id = %s order by timestamp desc limit 1', (card_id,))
        user = cursor.fetchone()

        if user:
            # If user exists, perform the desired actions
            username = user['username']
            user_id = user['user_id']
            print("username found: " + username)
        else:
            print("Username not found for the given card with ID " + card_id + ". Will send a slack message.")
            username = None
            user_id = None
            send_slack_message(f'Er is een nieuwe speler! Als jij net scande, reageer dan even met `ID: {card_id}`')

        # Fetch or iterate through the results to consume them
        # Example: results = cursor.fetchall()

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Ensure the cursor is closed
        cursor.close()
    
    if user:
        if not game_in_progress and username is not None and username not in players and len(players) < 3:
            players.add(username)
            print(f'Player {len(players)} joined the game.')
        
        elif not game_in_progress and username is not None and username not in players and len(players) == 3:
            players.add(username)
            print(f'Player {len(players)} joined the game.')
            game_in_progress = True

        elif game_in_progress and username in players:
            winners.add(username)
            winner_ids.add(user_id)
            print(f'Winner {len(winners)} confirmed.')
            players.remove(username)

            # Check if exactly two winners are identified
            if len(winners) == 1:
                game_winners = list(winners)
                game_winner_ids = list(winner_ids)
                losers = list(players)
                players = game_winners + losers

                # Assume Team1 wins
                print(f'Winners: {game_winners}!')
                
                # Update MySQL database with game results
                update_database_game_stats(players, game_winners)
                
                # Send winners to Slack
                send_slack_message(f'Congrats <@{" and <@".join(game_winner_ids)}> for winning the game!')
                
                # Reset game variables
                players.clear()
                losers.clear()
                winners.clear()
                game_in_progress = False
        elif not game_in_progress and username in players:
            print("Foutje. Speler al in het spel toegelaten.")
        elif game_in_progress and not username in players:
            print("Foutje. 5de speler of kaart die dus niet in huidig lopend spel zit.")
        else:
            print("Nog iets anders fout. Kan dat?")
    else:
        print("User nog known.")
    #db_connection.commit()

# Add user after first tag to the database, called from on_slack_message
def add_database_user(card_id, username, user_id, status):
    cursor = db_connection.cursor()

    # Check if the card_id already exists
    cursor.execute('SELECT * FROM players WHERE card_id = %s', (card_id,))
    existing_user = cursor.fetchone()

    if existing_user and status == "new":
        # If the card_id already exists, ignore
        print(f"User with card_id {card_id} already exists. Move on...")
        send_slack_message(f'Euh... De kaart met ID {card_id} werd al eerder toegevoegd. Wil je ze toch toevoegen, kan je het opnieuw posten met: `ADD ID: {card_id}`.')
    if existing_user and status == "update":
        cursor.execute('UPDATE players SET username = %s, user_id = %s WHERE card_id = %s', (username, user_id, card_id))
        db_connection.commit()
        print(f"User with card_id {card_id} added successfully.")
        send_slack_message(f'Welkom <@{user_id}>! We hebben de kaart aan jou gelinkt. Je kan vanaf nu deelnemen (je moet wel nog even opnieuw scannen).')

    else:
        # Insert the user into the database
        cursor.execute('INSERT INTO players (card_id, username, user_id) VALUES (%s, %s, %s)', (card_id, username, user_id))
        db_connection.commit()
        print(f"User with card_id {card_id} added successfully.")
        send_slack_message(f'Welkom <@{user_id}>! Je bent vanaf nu geregistreerd. Je kan vanaf nu deelnemen (je moet wel nog even opnieuw scannen).')

# Update MySQL database with game stats, called from on_card_tag
def update_database_game_stats(players, winners):
    cursor = db_connection.cursor()
    all_players = list(players)
    game_winners = list(winners)
    #cursor.execute('INSERT INTO game_stats (player1, player2, player3, player4, winner1, winner2) VALUES (%s, %s, %s, %s, %s, %s)',
    #               (*all_players, *game_winners))
    cursor.execute('INSERT INTO game_stats (player1, player2, winner1) VALUES (%s, %s, %s)',
                   (*all_players, *game_winners))
    
    result = cursor.fetchone()
    db_connection.commit()

# Generate and send weekly and monthly stats to Slack, called from running thread, polled every hour
def send_weekly_monthly_stats():
    while True:
        now = datetime.now()
        
        # Check if it's Friday at 6 PM for weekly stats
        if now.weekday() == 4 and now.hour == 18:
            send_stats_message('week')
            
        # Check if it's the last day of the month at 6 PM for monthly stats
        elif now.day == calendar.monthrange(now.year, now.month)[1] and now.hour == 18:
            send_stats_message('month')
        
        # Sleep for an hour
        time.sleep(3600)  # 1 hour

# Send stats message to Slack, polled from send_weekly_monthly_stats
def send_stats_message(time_period):
    cursor = db_connection.cursor(dictionary=True)
    
    # Calculate start date for the specified time_period
    if time_period == 'week':
        start_date = datetime.now() - timedelta(days=7)
    elif time_period == 'month':
        start_date = datetime(datetime.now().year, datetime.now().month, 1)
    
    # Most games won
    cursor.execute('''
        SELECT winner, COUNT(winner) as games_won
        FROM (
            SELECT winner1 as winner FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT winner2 as winner FROM game_stats WHERE timestamp >= %s
        ) AS winners
        GROUP BY winner
        ORDER BY games_won DESC
    ''', (start_date, start_date))
    most_wins = cursor.fetchall()
    
    # Most games played
    cursor.execute('''
        SELECT player, COUNT(player) as games_played
        FROM (
            SELECT player1 as player FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player2 as player FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player3 as player FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player4 as player FROM game_stats WHERE timestamp >= %s
        ) AS players
        GROUP BY player
        ORDER BY games_played DESC
    ''', (start_date, start_date, start_date, start_date))
    most_played = cursor.fetchall()
    
    # Relative ranking (most wins from games played)
    cursor.execute('''
        SELECT player, IFNULL(SUM(CASE WHEN winner IS NOT NULL THEN 1 ELSE 0 END), 0) / COUNT(player) AS win_ratio
        FROM (
            SELECT player1 as player, winner1 as winner FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player2 as player, winner2 as winner FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player3 as player, NULL as winner FROM game_stats WHERE timestamp >= %s
            UNION ALL
            SELECT player4 as player, NULL as winner FROM game_stats WHERE timestamp >= %s
        ) AS games
        GROUP BY player
        HAVING COUNT(player) > 0
        ORDER BY win_ratio DESC
    ''', (start_date, start_date, start_date, start_date))
    relative_ranking = cursor.fetchall()
    
    # Sort data by win ratio
    relative_ranking = sorted(relative_ranking, key=lambda x: x["win_ratio"], reverse=True)
    players = [player["username"] for player in relative_ranking]
    wins = [next(item["games_won"] for item in most_wins if item["username"] == player) for player in players]
    plays = [next(item["games_played"] for item in most_played if item["username"] == player) for player in players]
    win_ratio = [player["win_ratio"] for player in relative_ranking]
    
    image_stream = generate_stats_chart(players, wins, plays, win_ratio, time_period)
    # Upload the image to Slack
    upload_image_to_slack(image_stream)
    
    # Send the message to Slack
    #send_slack_message(message)
    #db_connection.commit()

def generate_stats_chart(players, wins, plays, win_ratio, time_period, start_date):
    # Generate Bar Chart
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Bar width
    bar_width = 0.2

    # Set position of bar on X axis
    r1 = range(len(players))
    r2 = [x + bar_width for x in r1]
    r3 = [x + bar_width for x in r2]

    # Create bars
    ax1.bar(r1, wins, color=COLOR_GAMES_WON, width=bar_width, edgecolor='grey', label='Games Won')
    ax1.bar(r2, plays, color=COLOR_GAMES_PLAYED, width=bar_width, edgecolor='grey', label='Games Played', bottom=wins)

    # Create twin Axes for win ratio
    ax2 = ax1.twinx()
    ax2.plot(r3, [ratio * 100 for ratio in win_ratio], color=COLOR_WIN_RATIO, marker='o', label='Win Ratio (%)')

    # Add xticks on the middle of the group bars
    ax1.set_xticks([r + bar_width for r in range(len(players))])
    ax1.set_xticklabels(players)

    ax1.set_xlabel('Players')
    ax1.set_ylabel('Games Won and Games Played')
    ax2.set_ylabel('Win Ratio (%)')

    # Set title based on time_period
    if time_period == 'week':
        week_number = datetime.now().strftime('%V')  # Use ISO week numbering
        year = datetime.now().year
        ax1.set_title(f'Weekly Stats for week {week_number}, {year}')
    elif time_period == 'month':
        month_name = calendar.month_name[datetime.now().month]
        year = datetime.now().year
        ax1.set_title(f'Monthly Stats for {month_name} {year}')

    ax1.spines['top'].set_visible(False)
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')

    # Save the chart as an image
    image_stream = BytesIO()
    plt.savefig(image_stream, format='png')
    image_stream.seek(0)
    plt.close()

    return image_stream

# Function to upload image to Slack
def upload_image_to_slack(image_stream):
    try:
        response = slack_client.files_upload(
            channels=CHANNEL_NAME,
            file=image_stream,
            title='Player Statistics',
            filename='player_stats.png',
            initial_comment='Player statistics for the week',
        )
        print(response)
    except SlackApiError as e:
        print(f"Error uploading image to Slack: {e.response['error']}")

class PrintObserver(CardObserver):
    def update(self, observable, actions):
        (addedcards, removedcards) = actions
        for card in addedcards:
            #print("+Inserted: ", toHexString(card.atr))
            card_id = toHexString(card.atr)
            on_card_read(card_id)
            time.sleep(3)

def start_nfc_reader():
    cardmonitor = CardMonitor()
    cardobserver = PrintObserver()
    cardmonitor.addObserver(cardobserver)

# Listen to Slack messages via slackeventsapi handler
@slack_events_adapter.on("message")
def on_message(payload):
    event = payload.get("event", {})
    channel = event.get("channel", "")
    user_id = event.get("user", "")
    user_data = get_user_info(user_id)
    username_in_full = user_data.get('profile', {}).get('display_name', '')
    text = event.get("text", "")
    print(f"on_message called - passing next items with username = '{username_in_full}'")
    on_slack_message(channel, username_in_full, user_id, text)

# Use the same port as you use for the ngrok service
def listen_to_slack():
    slack_events_adapter.start(port=3000)  

# Used to retrieve the username (instead of the user_id) to store in a database for readability
def get_user_info(user_id):
    api_url = 'https://slack.com/api/users.info'
    headers = {
        'Authorization': 'Bearer '+ SLACK_API_TOKEN_APP,
        'Content-Type': 'application/json'
    }
    params = {'user': user_id}

    response = requests.get(api_url, headers=headers, params=params)
    user_data = response.json().get('user', {})

    return user_data

# Main program
if __name__ == '__main__':
    # Initialize SQLAlchemy database
    initialize_database()

    # Start NFC reader and Slack listener
    nfc_thread = threading.Thread(target=start_nfc_reader)
    nfc_thread.start()

    # Start slack listener to make sure messages are received
    slack_listener_thread = threading.Thread(target=listen_to_slack)
    slack_listener_thread.start()
    
    # Start a thread to periodically send weekly and monthly stats to Slack
    stats_thread = threading.Thread(target=send_weekly_monthly_stats)
    stats_thread.start()

    # Wait for all threads to finish
    nfc_thread.join()
    slack_listener_thread.join()
    stats_thread.join()