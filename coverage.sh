#!/bin/bash

coverage run --parallel-mode --source=src src/irc_server &
sleep 5
coverage run --parallel-mode --source=src src/irc_bot &
coverage run --parallel-mode --source=src src/irc_bot &
wait %2
wait %3
kill -INT %1
coverage combine
