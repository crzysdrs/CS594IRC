[![Build Status](https://travis-ci.org/crzysdrs/CS594IRC.svg?branch=master)](https://travis-ci.org/crzysdrs/CS594IRC)
[![codecov.io](https://codecov.io/github/crzysdrs/CS594IRC/coverage.svg?branch=master)](https://codecov.io/github/crzysdrs/CS594IRC?branch=master)

# CS594IRC

Mitch Souders

This project is a simple IRC server and client combination that is similar to the existing [RFC1459](https://tools.ietf.org/html/rfc1459). The primary differences are the absence of federated connections between IRC servers and the usage of JSON in the basic IRC communication protocol. For more details about the underlying protocol, see the (unformatted) [RFC](rfc/rfc.mkd).

## Installation Instructions

If you are on Ubuntu you may need to install `python-numpy` via `apt-get`, since it requires other system packages to be installed.

```shell
pip install numpy              # Optional: Only needed for math_bot
python setup.py develop --user
```

To generate the fully formatted text RFC:

```shell
gem install kramdown-rfc2629 --user
sudo apt-get install xml2rfc -y
cd rfc && make
```

## Project Details
- **irc_server**  
The server process that provides a platform that can be connected to by multiple IRC clients.
- **irc_client**  
  Note: The client has the entrypoint: src/IRC/Client.py:main and not a specific script. This allows easy use of the client for creation of bots.  
  The client process that gives an easy to use interface to chat with other users on the same server. The client can be invoked with `--gui` for an ncurses interface. For a list of full commands in the IRC client type `/help`.
- **irc_bot**  
  Effectively a spam bot. This invokes 100 randomly generated commands to test the [coverage](https://codecov.io/github/crzysdrs/CS594IRC?branch=master) of a client and server pair.
- **math_bot**  
  A basic bot that responds to simple math equations when messaged directly at `mathbot` or any messages sent to `#math`.

## Note about Code Coverage

The code coverage stats could be higher if there was an easy way to automatically run the ncurses GUI as that is the primary cause of the lower coverage results.
