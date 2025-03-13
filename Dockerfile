FROM node:20.11-bookworm-slim AS node-image
FROM python:3.12.7-slim-bookworm

# Requirements for building packages
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        bzip2 ccache f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential libtool libltdl-dev \
        gnupg2 libdbus-glib-1-2 sudo sqlite3 \
        ninja-build jq xxd \
  && rm -rf /var/lib/apt/lists/*

# install autoconf 2.71, required by upstream libffi
RUN wget https://mirrors.ocf.berkeley.edu/gnu/autoconf/autoconf-2.71.tar.xz \
    && tar -xf autoconf-2.71.tar.xz \
    && cd autoconf-2.71 \
    && ./configure \
    && make install \
    && cp /usr/local/bin/autoconf /usr/bin/autoconf \
    && rm -rf autoconf-2.71

ADD requirements.txt /

WORKDIR /
RUN pip3 --no-cache-dir install -r requirements.txt \
    && rm requirements.txt

RUN cd / \
    && git clone --recursive https://github.com/WebAssembly/wabt \
    && cd wabt \
    && git submodule update --init \
    && make install-gcc-release-no-tests \
    && cd ~  \
    && rm -rf /wabt

COPY --from=node-image /usr/local/bin/node /usr/local/bin/
COPY --from=node-image /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN npm install -g \
  jsdoc \
  prettier \
  rollup \
  rollup-plugin-terser

# Normally, it is a bad idea to install rustup and cargo in
# system directories (it should not be shared between users),
# but this docker image is only for building packages, so I hope it is ok.
# Setting RUSTUP_UPDATE_ROOT gives us a beta rustup.
# TODO: Remove when Rustup 1.28.0 is released.
RUN wget -q -O  -  https://sh.rustup.rs | \
  RUSTUP_UPDATE_ROOT=https://dev-static.rust-lang.org/rustup \
  RUSTUP_HOME=/usr CARGO_HOME=/usr \
  sh -s -- -y --profile minimal --no-modify-path

# Get Chrome and Firefox (borrowed from https://github.com/SeleniumHQ/docker-selenium)

ARG CHROME_VERSION="latest"
ARG FIREFOX_VERSION="latest"
# Note: geckodriver version needs to be updated manually
ARG GECKODRIVER_VERSION="0.34.0"

#============================================
# Firefox & geckodriver
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
  && wget --no-verbose -O /tmp/firefox.tar.xz "$FIREFOX_DOWNLOAD_URL" \
  && tar -C /opt -xf /tmp/firefox.tar.xz \
  && rm /tmp/firefox.tar.xz \
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
  then CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE"); \
  else CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}"); \
  fi \
  && CHROME_DOWNLOAD_URL="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb" \
  && CHROMEDRIVER_DOWNLOAD_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION_FULL}/linux64/chromedriver-linux64.zip" \
  && wget --no-verbose -O /tmp/google-chrome.deb ${CHROME_DOWNLOAD_URL} \
  && apt-get update \
  && apt install -qqy /tmp/google-chrome.deb \
  && rm -f /tmp/google-chrome.deb \
  && rm -rf /var/lib/apt/lists/* \
  && wget --no-verbose -O /tmp/chromedriver-linux64.zip ${CHROMEDRIVER_DOWNLOAD_URL} \
  && unzip /tmp/chromedriver-linux64.zip -d /opt/ \
  && rm /tmp/chromedriver-linux64.zip \
  && ln -fs /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
  && echo "Using Chrome version: $(google-chrome --version)" \
  && echo "Using Chrome Driver version: $(chromedriver --version)"

CMD ["/bin/sh"]
WORKDIR /src
