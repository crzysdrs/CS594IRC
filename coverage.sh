#!/bin/bash
pkill -SIGINT -f irc_bot
pkill -SIGINT -f irc_server
pkill -SIGINT -f irc_client
pkill -SIGINT -f math_bot
killall -SIGINT coverage

coverage erase
sleep 1

mkdir -p log
echo "######### COVERAGE: Run in an expected behavior mode"
coverage run --parallel-mode --source=src src/irc_bot --log log/1.bot.noserver.log &
sleep 1
coverage run --parallel-mode --source=src src/irc_server --log log/1.server.log &
SERVER=$!
sleep 1
coverage run --parallel-mode --source=src src/irc_server --log log/1.server_exists.log &
sleep 5
coverage run --parallel-mode --source=src src/math_bot --log log/1.mathbot.log &
coverage run --parallel-mode --source=src src/irc_bot --log log/1.bot1.log &
BOT1=$!
sleep 2
coverage run --parallel-mode --source=src src/irc_bot --log log/1.bot2.log &
BOT2=$!
jobs -l
sleep 5
echo "######### COVERAGE: Waiting for BOT1,2"
wait ${BOT1} || exit 1
wait ${BOT2} || exit 1
echo "######### COVERAGE: Shutdown with one bot running"
coverage run --parallel-mode --source=src src/irc_bot --log log/1.bot3.log &
sleep 5
kill -INT ${SERVER} || exit 1
wait ${SERVER} || exit 1

sleep 2
echo "######### COVERAGE: Unexpected behavior mode, client/server unexpectedly dies"
coverage run --parallel-mode --source=src src/irc_server --log log/2.server.log &
SERVER=$!
sleep 5
coverage run --parallel-mode --source=src src/irc_bot --log log/2.bot1.log &
BOT1=$!
coverage run --parallel-mode --source=src src/irc_bot --log log/2.bot2.log &
BOT2=$!
jobs -l
sleep 2

echo "######### COVERAGE: Surpise Kill Client"
kill -9 ${BOT1} || exit 1
sleep 2
echo "######### COVERAGE: Surprise Kill Server"
kill -9 ${SERVER} || exit 1
echo "######### COVERAGE: Waiting for Bot2 to End"
wait ${BOT2} || exit 1

coverage combine
coverage report
