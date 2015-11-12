
all: rfc.txt

rfc.xml: rfc.mkd
	kramdown-rfc2629 rfc.mkd > rfc.xml

rfc.txt: rfc.xml
	xml2rfc rfc.xml
