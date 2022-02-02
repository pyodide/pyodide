FROM node:14.16.1-buster-slim AS node-image
FROM python:3.9.5-slim-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        # building packages
        bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential prelink autoconf libtool libltdl-dev \
        gnupg2 libdbus-glib-1-2 \
  && rm -rf /var/lib/apt/lists/*

ADD docs/requirements-doc.txt requirements.txt /

RUN pip3 --no-cache-dir install -r /requirements.txt \
  && pip3 --no-cache-dir install -r /requirements-doc.txt

# Get Chrome and Firefox (borrowed from https://github.com/SeleniumHQ/docker-selenium)

ENV CHROME_VERSION=${CHROME_VERSION:-"google-chrome-stable"}
ENV FIREFOX_VERSION=${FIREFOX_VERSION:-"latest"}
# Note: geckodriver version needs to be updated manually
ENV GECKODRIVER_VERSION="0.30.0"

#============================================
# Firefox & gekcodriver
#============================================
# can specify Firefox version by FIREFOX_VERSION;
#  e.g. latest
#       95.0b2
#       96.0
#
# can specify Firefox geckodriver version by GECKODRIVER_VERSION;
#============================================

RUN if [ $FIREFOX_VERSION = "latest" ] || [ $FIREFOX_VERSION = "nightly-latest" ] || [ $FIREFOX_VERSION = "devedition-latest" ] || [ $FIREFOX_VERSION = "esr-latest" ]; \
  then FIREFOX_DOWNLOAD_URL="https://download.mozilla.org/?product=firefox-$FIREFOX_VERSION-ssl&os=linux64&lang=en-US"; \
  else FIREFOX_DOWNLOAD_URL="https://download-installer.cdn.mozilla.net/pub/firefox/releases/$FIREFOX_VERSION/linux-x86_64/en-US/firefox-$FIREFOX_VERSION.tar.bz2"; \
  fi \
  && wget --no-verbose -O /tmp/firefox.tar.bz2 $FIREFOX_DOWNLOAD_URL \
  && tar -C /opt -xjf /tmp/firefox.tar.bz2 \
  && rm /tmp/firefox.tar.bz2 \
  && mv /opt/firefox /opt/firefox-$FIREFOX_VERSION \
  && ln -fs /opt/firefox-$FIREFOX_VERSION/firefox /usr/local/bin/firefox \
  && wget --no-verbose -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v$GECKODRIVER_VERSION/geckodriver-v$GECKODRIVER_VERSION-linux64.tar.gz \
  && rm -rf /opt/geckodriver \
  && tar -C /opt -zxf /tmp/geckodriver.tar.gz \
  && rm /tmp/geckodriver.tar.gz \
  && mv /opt/geckodriver /opt/geckodriver-$GECKODRIVER_VERSION \
  && chmod 755 /opt/geckodriver-$GECKODRIVER_VERSION \
  && ln -fs /opt/geckodriver-$GECKODRIVER_VERSION /usr/local/bin/geckodriver \
  && echo "Using Firefox version: $(firefox --version)" \
  && echo "Using GeckoDriver version: "$GECKODRIVER_VERSION


#============================================
# Google Chrome & Chrome webdriver
#============================================
# can specify Chrome version by CHROME_VERSION;
#  e.g. google-chrome-stable=53.0.2785.101-1
#       google-chrome-beta=53.0.2785.92-1
#       google-chrome-unstable=54.0.2840.14-1
#       latest (equivalent to google-chrome-stable)
#       google-chrome-beta  (pull latest beta)
#
# can specify Chrome webdriver version by CHROME_DRIVER_VERSION;
# Latest released version will be used by default
#============================================

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update -qqy \
  && apt-get -qqy install \
    ${CHROME_VERSION:-google-chrome-stable} \
  && rm /etc/apt/sources.list.d/google-chrome.list \
  && rm -rf /var/lib/apt/lists/* /var/cache/apt/* \
  && CHROME_MAJOR_VERSION=$(google-chrome --version | sed -E "s/.* ([0-9]+)(\.[0-9]+){3}.*/\1/") \
  && CHROME_DRIVER_VERSION=$(wget --no-verbose -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR_VERSION}"); \
  && wget --no-verbose -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip \
  && rm -rf /opt/selenium/chromedriver \
  && unzip /tmp/chromedriver_linux64.zip -d /opt/selenium \
  && rm /tmp/chromedriver_linux64.zip \
  && mv /opt/selenium/chromedriver /opt/selenium/chromedriver-$CHROME_DRIVER_VERSION \
  && chmod 755 /opt/selenium/chromedriver-$CHROME_DRIVER_VERSION \
  && ln -fs /opt/selenium/chromedriver-$CHROME_DRIVER_VERSION /usr/local/bin/chromedriver \
  && echo "Using Chrome version: $(google-chrome --version)" \
  && echo "Using Chromedriver version: "$CHROME_DRIVER_VERSION

COPY --from=node-image /usr/local/bin/node /usr/local/bin/
COPY --from=node-image /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN npm install -g \
  jsdoc \
  prettier \
  rollup \
  rollup-plugin-terser

CMD ["/bin/sh"]
WORKDIR /src
