FROM node:14.16.1-buster-slim AS node-image
FROM python:3.9.5-slim-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
        # building packages
        bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
        patch pkg-config swig unzip wget xz-utils \
        autoconf autotools-dev automake texinfo dejagnu \
        build-essential prelink autoconf libtool libltdl-dev \
        # following packages are is necessary for running chromium
        libgconf-2-4 libnss3 libxcb1\
  && rm -rf /var/lib/apt/lists/*

ADD docs/requirements-doc.txt requirements.txt /

ENV PATH="${PATH}:/chrome/"

RUN pip3 --no-cache-dir install -r /requirements.txt \
  && pip3 --no-cache-dir install -r /requirements-doc.txt

# Get firefox and geckodriver
RUN wget -qO- https://ftp.mozilla.org/pub/firefox/releases/94.0.1/linux-x86_64/en-US/firefox-94.0.1.tar.bz2 | tar jx \
  && ln -s $PWD/firefox/firefox /usr/local/bin/firefox \
  && wget -qO- https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz | tar zxC /usr/local/bin/ \
  && geckodriver --version

# Get a recent version of Chromium and chromedriver
# Follow https://askubuntu.com/a/1112729 to get the download links
RUN wget --quiet "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F911577%2Fchrome-linux.zip?generation=1628818639642035&alt=media" -O chrome-linux.zip \
  && unzip chrome-linux.zip \
  && mv chrome-linux /chrome/ \
  && wget --quiet "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F911577%2Fchromedriver_linux64.zip?generation=1628818644201948&alt=media" -O chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv $PWD/chromedriver_linux64/chromedriver /chrome/ \
  && rm -f chromedriver_linux64.zip chrome-linux.zip \
  && chromedriver --version

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
