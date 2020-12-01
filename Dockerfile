FROM python:3.8.2-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
                  # building packages
                  bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran libtinfo5 node-less swig uglifyjs \
                  # testing packages: libgconf-2-4 is necessary for running chrome
                  libgconf-2-4 chromium firefox-esr \
  && rm -rf /var/lib/apt/lists/* \
  && test "Comment: Hardcode nodejs path for uglifyjs, so it doesn't conflict with emcc's nodejs" \
  && test $(which node) = /usr/bin/node && test $(which uglifyjs) = /usr/bin/uglifyjs \
  && echo '#!/bin/sh -e\nexec /usr/bin/node /usr/bin/uglifyjs "$@"' >/tmp/uglifyjs \
  && chmod a+x /tmp/uglifyjs && mv -t /usr/local/bin /tmp/uglifyjs

RUN pip3 --no-cache-dir install pytest pytest-xdist pytest-instafail pytest-rerunfailures selenium PyYAML flake8

# Get recent version of geckodriver
RUN wget -qO- https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-linux64.tar.gz | tar zxC /usr/local/bin/

# Get recent version of chromedriver
RUN wget --quiet https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv $PWD/chromedriver /usr/local/bin \
  && rm -f chromedriver_linux64.zip

CMD ["/bin/sh"]
WORKDIR /src
