FROM node:14.16.1-buster-slim AS node-image
FROM python:3.8.2-slim-buster

RUN apt-get update
# building packages
RUN apt-get install -y --no-install-recommends \
  bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
  patch pkg-config swig unzip wget xz-utils

# testing packages: libgconf-2-4 is necessary for running chromium
RUN apt-get install -y --no-install-recommends \
    libgconf-2-4 chromium

# Get firefox 70.0.1 and geckodriver
RUN wget -qO- https://ftp.mozilla.org/pub/firefox/releases/87.0/linux-x86_64/en-US/firefox-87.0.tar.bz2 | tar jx \
  && ln -s $PWD/firefox/firefox /usr/local/bin/firefox \
  && wget -qO- https://github.com/mozilla/geckodriver/releases/download/v0.29.1/geckodriver-v0.29.1-linux64.tar.gz | tar zxC /usr/local/bin/

# Get recent version of chromedriver
RUN wget --quiet https://chromedriver.storage.googleapis.com/89.0.4389.23/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv $PWD/chromedriver /usr/local/bin \
  && rm -f chromedriver_linux64.zip

# Copy node install from node-image
COPY --from=node-image /usr/local/bin/node /usr/local/bin/
COPY --from=node-image /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
RUN ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN rm -rf /var/lib/apt/lists/*

RUN pip3 --no-cache-dir install \
  pytest \
  pytest-cov \
  pytest-httpserver \
  pytest-instafail \
  pytest-rerunfailures \
  pytest-xdist \
  "selenium==4.0.0.b3"

RUN pip3 --no-cache-dir install \
  black \
  "cython<3.0" \
  packaging \
  flake8 \
  hypothesis \
  "mypy==0.812" \
  pyyaml

RUN npm install -g \
  jsdoc \
  uglify-js \
  prettier \
  rollup \
  rollup-plugin-terser


CMD ["/bin/sh"]
WORKDIR /src
