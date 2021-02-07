FROM python:3.8.2-slim-buster

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
                  # building packages
                  bzip2 ccache clang-format-6.0 cmake f2c g++ gfortran git make \
                  patch pkg-config swig unzip wget xz-utils \
                  # testing packages: libgconf-2-4 is necessary for running chromium
                  libgconf-2-4 chromium \
  && rm -rf /var/lib/apt/lists/*

RUN pip3 --no-cache-dir install pytest pytest-xdist pytest-instafail pytest-rerunfailures \
      pytest-httpserver pytest-cov PyYAML flake8 black distlib mypy "Cython<3.0" && \
      # install latest pre-release version of selenium
      pip3 --no-cache-dir install --pre selenium

# Get firefox 70.0.1 and geckodriver
RUN wget -qO- https://ftp.mozilla.org/pub/firefox/releases/85.0.1/linux-x86_64/en-US/firefox-85.0.1.tar.bz2 | tar jx \
  && ln -s $PWD/firefox/firefox /usr/local/bin/firefox \
  && wget -qO- https://github.com/mozilla/geckodriver/releases/download/v0.29.0/geckodriver-v0.29.0-linux64.tar.gz | tar zxC /usr/local/bin/

# Get recent version of chromedriver
RUN wget --quiet https://chromedriver.storage.googleapis.com/87.0.4280.88/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv $PWD/chromedriver /usr/local/bin \
  && rm -f chromedriver_linux64.zip

CMD ["/bin/sh"]
WORKDIR /src
