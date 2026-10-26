.PHONY: preview run check

preview:
	python3 -m http.server 8787 --directory dist --bind 127.0.0.1

run:
	python3 bridge.py

check:
	python3 -m unittest -v test_bridge.py
	node --check dist/app.js
