#!/bin/bash

# Start ngrok on port 3000
ngrok http --domain=firm-wahoo-equally.ngrok-free.app 3000 &

# Start TightVNC
tightvncserver &

# Set your environment variables
source /home/bartmuskala/Documents/NFC-KICKERBOT/set_env.sh &

# Start your Python script
python /home/bartmuskala/Documents/NFC-KICKERBOT/nfcbot.py &