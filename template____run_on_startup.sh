#!/bin/bash

# Start ngrok on port 3000
ngrok http --domain=change-this-part.ngrok-free.app 3000 &

# Start TightVNC
tightvncserver &

# Set your environment variables
source /path/to/NFC-kickerbot/set_env.sh &

# Start your Python script
python /path/to/NFC-kickerbot/nfcbot.py &