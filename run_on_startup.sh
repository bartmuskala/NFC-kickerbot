#!/bin/bash

# Start ngrok on port 3000
ngrok http --domain=firm-wahoo-equally.ngrok-free.app 3000 &

# Start TightVNC
tightvncserver &

# Start your Python script
python /home/bartmuskala/Documents/Coding/nfc-bot-final.py &