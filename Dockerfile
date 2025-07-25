FROM ubuntu:25.04 AS selenium-manager-image
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates curl jq wget \
  && rm -rf /var/lib/apt/lists/*

ARG SELENIUM_MANAGER_VERSION=latest
RUN SELENIUM_MANAGER_VERSION_FULL=$(curl -s https://api.github.com/repos/SeleniumHQ/selenium_manager_artifacts/releases/${SELENIUM_MANAGER_VERSION} | jq -r .name) \
  && wget --no-verbose https://github.com/SeleniumHQ/selenium_manager_artifacts/releases/download/${SELENIUM_MANAGER_VERSION_FULL}/selenium-manager-linux \
  && chmod +x selenium-manager-linux \
  && mv selenium-manager-linux /usr/local/bin/selenium-manager

ARG CHROME_VERSION="latest"
ARG FIREFOX_VERSION="latest"
# Note: geckodriver version needs to be updated manually
ARG GECKODRIVER_VERSION="0.34.0"

RUN if [ $FIREFOX_VERSION = "latest" ]; then SE_FIREFOX_VERSION="stable"; \
  else SE_FIREFOX_VERSION=${FIREFOX_VERSION}; \
  fi \
  && export SE_FIREFOX_VERSION \
  && export SE_GECKODRIVER_VERSION=${GECKODRIVER_VERSION} \
  && SE_FIREFOX_OUTPUT=$(selenium-manager --browser firefox --driver gecko --output json) \
  && SE_FIREFOX_BROWSER_PATH=$(echo ${SE_FIREFOX_OUTPUT} | jq -r '.result.browser_path') \
  && SE_GECKO_DRIVER_PATH=$(echo ${SE_FIREFOX_OUTPUT} | jq -r '.result.driver_path') \
  && mv $(dirname ${SE_FIREFOX_BROWSER_PATH}) /opt/firefox \
  && mv $(dirname ${SE_GECKO_DRIVER_PATH}) /opt/geckodriver

RUN if [ $CHROME_VERSION = "latest" ]; then SE_CHROME_VERSION="stable"; \
  else SE_CHROME_VERSION=${CHROME_VERSION}; \
  fi \
  && export SE_CHROME_VERSION \
  && SE_CHROME_OUTPUT=$(selenium-manager --browser chrome --driver chrome --output json) \
  && SE_CHROME_BROWSER_PATH=$(echo ${SE_CHROME_OUTPUT} | jq -r '.result.browser_path') \
  && SE_CHROME_DRIVER_PATH=$(echo ${SE_CHROME_OUTPUT} | jq -r '.result.driver_path') \
  && mv $(dirname ${SE_CHROME_BROWSER_PATH}) /opt/chrome \
  && mv $(dirname ${SE_CHROME_DRIVER_PATH}) /opt/chromedriver


FROM node:20.11-bookworm-slim AS node-image
FROM python:3.13.2-slim-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        # Requirements for building packages \
        bzip2 ccache f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential libltdl-dev \
        gnupg2 libdbus-glib-1-2 sudo sqlite3 \
        ninja-build jq cmake bison \
        # Dependencies of Chrome and Firefox \
        ca-certificates fonts-liberation libasound2 \
        libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
        libc6 libcairo2 libcups2 libcurl4 libdbus-1-3 \
        libexpat1 libgbm1 libglib2.0-0 libnspr4 libnss3 \
        libpango-1.0-0 libudev1 libvulkan1 libx11-6 \
        libxcb1 libxcomposite1 libxdamage1 libxext6 \
        libxfixes3 libxkbcommon0 libxrandr2 xdg-utils \
        libgtk-3-0 libx11-xcb1 libtool \
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

COPY --from=selenium-manager-image /opt/firefox /opt/firefox
COPY --from=selenium-manager-image /opt/geckodriver /opt/geckodriver
COPY --from=selenium-manager-image /opt/chrome /opt/chrome
COPY --from=selenium-manager-image /opt/chromedriver /opt/chromedriver

RUN ln -fs /opt/firefox/firefox /usr/local/bin/firefox \
  && ln -fs /opt/geckodriver/geckodriver /usr/local/bin/geckodriver \
  && ln -fs /opt/chrome/chrome /usr/local/bin/chrome \
  && ln -fs /opt/chromedriver/chromedriver /usr/local/bin/chromedriver \
  && echo "Using Firefox version: $(firefox --version)" \
  && echo "Using GeckoDriver version: $(geckodriver --version)" \
  && echo "Using Chrome version: $(chrome --version)" \
  && echo "Using Chrome Driver version: $(chromedriver --version)"

CMD ["/bin/sh"]
WORKDIR /src
