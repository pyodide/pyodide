FROM node:20.11-bookworm-slim AS node-image
FROM python:3.13.2-slim-bookworm

ARG TARGETPLATFORM

# Requirements for building packages
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        bzip2 ccache f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential libltdl-dev \
        gnupg2 libdbus-glib-1-2 sudo sqlite3 \
        ninja-build jq cmake bison \
  && rm -rf /var/lib/apt/lists/*

# install autoconf 2.72, required by upstream libffi
RUN wget https://mirrors.ocf.berkeley.edu/gnu/autoconf/autoconf-2.72.tar.xz \
    && tar -xf autoconf-2.72.tar.xz \
    && cd autoconf-2.72 \
    && ./configure \
    && make install \
    && cp /usr/local/bin/autoconf /usr/bin/autoconf \
    && cd .. \
    && rm -rf autoconf-2.72*

# install libtool 2.5.4, required by ngspice for emscripten support
RUN wget https://mirrors.ocf.berkeley.edu/gnu/libtool/libtool-2.5.4.tar.xz \
    && tar -xf libtool-2.5.4.tar.xz \
    && cd libtool-2.5.4 \
    && ./configure \
    && make install \
    && cd .. \
    && rm -rf libtool-2.5.4*

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
# Available for Linux amd64 and Linux arm64
#============================================
# can specify Firefox version by FIREFOX_VERSION;
#  e.g. latest
#       95
#       96
#
# can specify Firefox geckodriver version by GECKODRIVER_VERSION;
#============================================

# https://download.mozilla.org/?product=firefox-nightly-latest-ssl&os=linux64-aarch64&lang=en-US

RUN \
  # Handle GeckoDriver architecture
  set -e -x && \
  if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
    GECKODRIVER_ARCH="linux64"; \
  elif [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    GECKODRIVER_ARCH="linux-aarch64"; \
  else \
    echo "Unsupported platform: $TARGETPLATFORM"; \
    exit 1; \
  fi \
  # Handle Firefox version based on FIREFOX_VERSION and Linux amd64
  && if [ "$FIREFOX_VERSION" = "latest" ] || [ "$FIREFOX_VERSION" = "nightly-latest" ] || [ "$FIREFOX_VERSION" = "devedition-latest" ] || [ "$FIREFOX_VERSION" = "esr-latest" ]; then \
    FIREFOX_DOWNLOAD_URL="https://download.mozilla.org/?product=firefox-$FIREFOX_VERSION-ssl&os=linux64&lang=en-US"; \
  else \
    FIREFOX_VERSION_FULL="${FIREFOX_VERSION}.0" \
    && FIREFOX_DOWNLOAD_URL="https://download-installer.cdn.mozilla.net/pub/firefox/releases/$FIREFOX_VERSION_FULL/linux-x86_64/en-US/firefox-$FIREFOX_VERSION_FULL.tar.bz2"; \
  fi && \
  # Handle Firefox version based on FIREFOX_VERSION and Linux arm64. Here we use
  # "nightly-latest", because it is the only one available for arm64 (as of 13/08/2024)
  # TODO: Simplify this when Firefox non-nightlies are available for arm64
  if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    echo "Note: Firefox is available as nightly-latest on Linux arm64, using it and ignoring $FIREFOX_VERSION"; \
    FIREFOX_VERSION="nightly-latest"; \
    FIREFOX_DOWNLOAD_URL="https://download.mozilla.org/?product=firefox-$FIREFOX_VERSION-ssl&os=linux64-aarch64&lang=en-US"; \
  fi \
  && wget --no-verbose -O /tmp/firefox.tar.xz $FIREFOX_DOWNLOAD_URL \
  && tar -C /opt -xf /tmp/firefox.tar.xz \
  && rm /tmp/firefox.tar.xz \
  && mv /opt/firefox /opt/firefox-$FIREFOX_VERSION \
  && ln -fs /opt/firefox-$FIREFOX_VERSION/firefox /usr/local/bin/firefox \
  && wget --no-verbose -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v$GECKODRIVER_VERSION/geckodriver-v$GECKODRIVER_VERSION-$GECKODRIVER_ARCH.tar.gz \
  && rm -rf /opt/geckodriver \
  && tar -C /opt -zxf /tmp/geckodriver.tar.gz \
  && rm /tmp/geckodriver.tar.gz \
  && mv /opt/geckodriver /opt/geckodriver-$GECKODRIVER_VERSION \
  && chmod 755 /opt/geckodriver-$GECKODRIVER_VERSION \
  && ln -fs /opt/geckodriver-$GECKODRIVER_VERSION /usr/local/bin/geckodriver \
  && echo "Using Firefox version: $(firefox --version)" \
  && echo "Using GeckoDriver version: $GECKODRIVER_VERSION, built for $GECKODRIVER_ARCH"


#============================================
# Google Chrome & Chrome webdriver
# This is currently for Linux amd64 only
#
#============================================
# can specify Chrome version by CHROME_VERSION;
#  e.g. latest
#       96
#       97
#============================================

RUN set -e -x \
    && if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        echo "Chrome and Chrome web driver aren't currently supported on arm64, skipping installation" \
        && exit 0; \
    fi \
    && if [ "$CHROME_VERSION" = "latest" ]; then \
        CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE"); \
    else \
        CHROME_VERSION_FULL=$(wget --no-verbose -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}"); \
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
