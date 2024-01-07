# NFC KICKERBOT

## The NFC Kickerbot in a nutshell

The NFC Kickerbot is a simple system to allow participants of a kickergame (or any game) to identify themselves with the simple tag of an NFC card, token or device (e.g. a smartphone). Once registered via a Slack interface, they can play the game. Winners tag again and are stored in a local mysql database system. Every week and month, stats are shared via the same slack channel with a simple Matplotlib generated graph.

## What you'll need

The kickerbot only works, if you have...

- an NFC enabled card reader. Beware: there are multiple out there and all work with different libraries. I used the [DL533R from Digital Logic](https://www.nfc-tag-shop.de/en/NFC-Reader-Writer-DL533R-IP54-white-green-with-range-booster/68949) (beware: is has an R, the N version works with libnfc which requires the pynfc library instead of pyscard). Don't buy the ACS ARC122U device as this has some known issues.
- [Slack](https://slack.com/) as a communications tool
- a [Raspberry Pi](https://www.raspberrypi.com/) or other solution to connect the USB-NFC reader to. We have used a 4(00) device, the new 5 should be faster yet is not required :-).

## Installation steps

### Dependencies

Ensure you have Python installed (it will also install the other libraries that you import in the script).

- [matplotlib](https://matplotlib.org/): Matplotlib is a 2D plotting library for creating static, animated, and interactive visualizations in Python. It is used to generate a nice graph with stats.
- [mysql-connector-python](https://dev.mysql.com/doc/connector-python/en/): MySQL Connector/Python is implementing the MySQL Client/Server protocol completely in Python.
- [slackeventsapi](https://github.com/slackapi/python-slack-events-api): A Python package that allows your ngrok server to listen to messages sent in a specific channel.
- [slack_sdk](https://github.com/slackapi/python-slack-sdk): A python packafe for building apps on the Slack Platform. It is used to get data about users such as their display name.
- [pyscard](https://github.com/LudovicRousseau/pyscard): pyscard is a Python module for working with smart cards and the NFC reader I used. In case of troubles, check their [setup details](https://github.com/LudovicRousseau/pyscard/blob/master/INSTALL.md). Depending on your reader, you might need other libraries such as nfcpy, pynfc or nfclib.

For external libraries, you can use the following commands to install them using pip:

    pip install matplotlib mysql-connector-python slackeventsapi slack_sdk swig pyscard 

You might run into some other requirements, but they are clearly indicated in the error messages normally.

### Set up a slack bot

The bot is required to share messages in a slack channel where it asks users to identify themselves.

1. [Set up a slack bot](https://api.slack.com/apps).
2. Make sure to retrieve the slackbot token from the 'OAuth & Permissions' tab and your signing key from 'Basic information'.
3. Set the necessary permissions. Although not all might be required, it is not harmful to do so: app_mentions:read, channels:history, channels:read, chat:write, chat:write.public, commands, files:write, im:history, im:read, im:write, incoming-webhook, users:read.
4. Create a channel in your Slack workspace where you will install the bot. 
5. Install the bot to the channel.

The bot key you need (not to be confused with a user key) starts with 'xoxb'.
Add the slack channel's name to the **nfcbot.py** code:

    CHANNEL_NAME = '#channel-name'

Add the slack credentials to the **set_env.sh** script. Use the provided template **(example____set_env.sh)** and remove the example____ part.
    SLACK_API_TOKEN_APP=xoxb-xxx
    SIGNING_SECRET=xxx

### Set up a MySQL database

Set up a MySQL database and make sure to provide the details to the script. 
Add the details to the **nfcbot.py** code:

    MYSQL_HOST = '127.0.0.1' # or localhost
    MYSQL_DATABASE = 'your_database_name'

Add your credentials in the **set_env.sh** script for safety reasons:

    MYSQL_USER=your_username
    MYSQL_PASSWORD=your_password

A simple solution is to give 'your_database_name' as an argument to the script from [mattbell87](https://gist.github.com/mattbell87/1e678cc850e0ed66444b02a8cb6a094f).

    ./create-mysql.bash your_database_name

### Validate your set_env.sh file

The file should look like this:

    # set_env.sh

    export SLACK_API_TOKEN_APP=xoxb-app-token
    export SIGNING_SECRET=signing-key-from-slack
    export MYSQL_USER=your-user
    export MYSQL_PASSWORD=your-password

### Set up your colors :) 

If you are nitpicky about the color scheme used, you can change it in the code :).

    COLOR_GAMES_WON = '#53b4c5'  # Games Won color (Blue)
    COLOR_GAMES_PLAYED = '#b2eaf2'  # Games Played color (Green)
    COLOR_WIN_RATIO = '#e65000'  # Win Ratio color (Red)

### Set up an ngrok account (or similar)
The Ngrok account makes sure that the slackeventsapi can listen to messages sent in a specific channel. The script expects users to identify them via a Slack message.

1. Surf to https://ngrok.com/ and make an account
2. Install ngrok on your Raspberry Pi or other system as indicated on the dashboard page. I used Snap that I installed via:
    sudo apt update
    sudo apt install snapd
    sudo reboot
3. Bind your key to the server. The key can be found in ['Getting Started - Your Authtoken'](https://dashboard.ngrok.com/get-started/your-authtoken). Use the following command in your terminal:
    ngrok config add-authtoken your_key
4. I like to use a static domain, you can choose that on the dashboard page

### Add 'Run on startup' script
Put the 'run_on_startup.sh' script in the "etc/network/if-up.d/" folder.
Files in this folder are executed when the network is up.

    #!/bin/bash
    
    # Start ngrok service on port 3000, make sure to replace with your unique URL. The port is the port used in the main script.
    ngrok http --domain=firm-wahoo-equally.ngrok-free.app 3000 &
    
    # Start TightVNC, this is optional but easy to have when you want a GUI. You still have to set it up via sudo apt-get install tightvncserver

    tightvncserver &

    # Set your environment variables
    source /your_path/to/file/set_env.sh &
    
    # Start your Python script
    python /your_path/to/file/nfcbot.py &

What the script does:
1. start an ngrok service so the slackeventsapi is accessible from anywhere
2. start a VNC service so you can access the device (optional)
3. start the kickerbot script, make sure to adjust the file location and the right name

### Reboot and test

If things go wrong, it might be many things including...
- the NFC-device is of a different type and requires another library
- your bot doesn't have the necessary permissions
- your ngrok service is not running on the right port
- your firewall is too strict, allow the port to be used
- not all dependencies are installed properly
- you run a python version that is too old or too new
- ...