FROM node:14.16.1-buster-slim AS node-image
FROM python:3.9.5-slim-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        # building packages
        bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential prelink autoconf libtool libltdl-dev \
        # testing packages: libgconf-2-4 is necessary for running chromium
        libgconf-2-4 "chromium=90.*" \
  && rm -rf /var/lib/apt/lists/*

ADD docs/requirements-doc.txt requirements.txt /

RUN pip3 --no-cache-dir install -r /requirements.txt \
  && pip3 --no-cache-dir install -r /requirements-doc.txt

# Get firefox 70.0.1 and geckodriver
RUN wget -qO- https://ftp.mozilla.org/pub/firefox/releases/87.0/linux-x86_64/en-US/firefox-87.0.tar.bz2 | tar jx \
  && ln -s $PWD/firefox/firefox /usr/local/bin/firefox \
  && wget -qO- https://github.com/mozilla/geckodriver/releases/download/v0.29.1/geckodriver-v0.29.1-linux64.tar.gz | tar zxC /usr/local/bin/

# Get recent version of chromedriver
RUN wget --quiet https://chromedriver.storage.googleapis.com/90.0.4430.24/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv $PWD/chromedriver /usr/local/bin \
  && rm -f chromedriver_linux64.zip

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
