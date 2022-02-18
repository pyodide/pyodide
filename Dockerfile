FROM node:14.16.1-buster-slim AS node-image
FROM python:3.9.5-slim-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        # building packages
        bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential prelink autoconf libtool libltdl-dev \
        gnupg2 libdbus-glib-1-2

ADD docs/requirements-doc.txt requirements.txt /

RUN pip3 --no-cache-dir install -r /requirements.txt \
  && pip3 --no-cache-dir install -r /requirements-doc.txt

# Get Chrome and Firefox (borrowed from https://github.com/SeleniumHQ/docker-selenium)

ARG CHROME_VERSION="latest"
ARG FIREFOX_VERSION="latest"
# Note: geckodriver version needs to be updated manually
ARG GECKODRIVER_VERSION="0.30.0"

#============================================
# Firefox & gekcodriver
#============================================
# can specify Firefox version by FIREFOX_VERSION;
#  e.g. latest
#       95
#       96
#
# can specify Firefox geckodriver version by GECKODRIVER_VERSION;
#============================================

RUN if [ $FIREFOX_VERSION = "latest" ] || [ $FIREFOX_VERSION = "nightly-latest" ] || [ $FIREFOX_VERSION = "devedition-latest" ] || [ $FIREFOX_VERSION = "esr-latest" ]; \
  then FIREFOX_DOWNLOAD_URL="https://download.mozilla.org/?product=firefox-$FIREFOX_VERSION-ssl&os=linux64&lang=en-US"; \
  else FIREFOX_VERSION_FULL="${FIREFOX_VERSION}.0" && FIREFOX_DOWNLOAD_URL="https://download-installer.cdn.mozilla.net/pub/firefox/releases/$FIREFOX_VERSION_FULL/linux-x86_64/en-US/firefox-$FIREFOX_VERSION_FULL.tar.bz2"; \
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
#  e.g. latest
#       96
#       97
#============================================

RUN if [ $CHROME_VERSION = "latest" ]; \
  then CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"); \
  else CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}"); \
  fi \
  && CHROME_DOWNLOAD_URL="https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION_FULL}-1_amd64.deb" \
  && wget --no-verbose -O /tmp/google-chrome.deb ${CHROME_DOWNLOAD_URL} \
  && apt install -qqy /tmp/google-chrome.deb \
  && rm -f /tmp/google-chrome.deb \
  && rm -rf /var/lib/apt/lists/* \
  && wget --no-verbose -O /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/$CHROME_VERSION_FULL/chromedriver_linux64.zip \
  && rm -rf /opt/selenium/chromedriver \
  && unzip /tmp/chromedriver_linux64.zip -d /opt/selenium \
  && rm /tmp/chromedriver_linux64.zip \
  && mv /opt/selenium/chromedriver /opt/selenium/chromedriver-$CHROME_VERSION_FULL \
  && chmod 755 /opt/selenium/chromedriver-$CHROME_VERSION_FULL \
  && ln -fs /opt/selenium/chromedriver-$CHROME_VERSION_FULL /usr/local/bin/chromedriver \
  && echo "Using Chrome version: $(google-chrome --version)" \
  && echo "Using Chromedriver version: "$CHROME_VERSION_FULL

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
