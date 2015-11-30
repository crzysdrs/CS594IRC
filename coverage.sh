#!/bin/bash

echo "######### COVERAGE: Run in an expected behavior mode"
coverage run --parallel-mode --source=src src/irc_server &
SERVER=$!
sleep 5
coverage run --parallel-mode --source=src src/irc_bot &
BOT1=$!
sleep 2
coverage run --parallel-mode --source=src src/irc_bot &
BOT2=$!
jobs -l
sleep 5
echo "######### COVERAGE: Waiting for BOT1,2"
wait ${BOT1}
wait ${BOT2}
echo "######### COVERAGE: Shutdown with one bot running"
coverage run --parallel-mode --source=src src/irc_bot &
sleep 5
kill -INT ${SERVER}
wait ${SERVER}

sleep 2
echo "######### COVERAGE: Unexpected behavior mode, client/server unexpectedly dies"
coverage run --parallel-mode --source=src src/irc_server &
SERVER=$!
sleep 5
coverage run --parallel-mode --source=src src/irc_bot &
BOT1=$!
sleep 2
coverage run --parallel-mode --source=src src/irc_bot &
BOT2=$!
jobs -l
sleep 10

echo "######### COVERAGE: Surpise Kill Client"
kill -9 ${BOT1}
sleep 2
echo "######### COVERAGE: Surprise Kill Server"
kill -9 ${SERVER}
echo "######### COVERAGE: Waiting for Bot2 to End"
wait ${BOT2}

coverage combine
