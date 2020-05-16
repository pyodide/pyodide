FROM circleci/python:3.7.7-buster

RUN sudo apt-get update \
  # bzip2 and libgconf-2-4 are necessary for extracting firefox and running chrome, respectively
  && sudo apt-get install bzip2 libgconf-2-4 node-less cmake build-essential clang-format-6.0 \
                  uglifyjs chromium ccache libncurses6 gfortran f2c g++-8 \
  && sudo apt-get clean \
  && sudo apt-get autoremove \
  && sudo ln -s /usr/bin/clang-format-6.0 /usr/bin/clang-format

RUN sudo pip install pytest pytest-xdist pytest-instafail selenium PyYAML flake8 \
    && sudo rm -rf /root/.cache/pip

# Get recent version of Firefox and geckodriver
RUN sudo wget --quiet -O firefox.tar.bz2 https://download.mozilla.org/\?product\=firefox-latest-ssl\&os\=linux64\&lang\=en-US \
  && sudo tar jxf firefox.tar.bz2 \
  && sudo rm -f /usr/local/bin/firefox \
  && sudo ln -s $PWD/firefox/firefox /usr/local/bin/firefox \
  && sudo wget --quiet https://github.com/mozilla/geckodriver/releases/download/v0.21.0/geckodriver-v0.21.0-linux64.tar.gz \
  && sudo tar zxf geckodriver-v0.21.0-linux64.tar.gz -C /usr/local/bin \
  && sudo rm -f firefox.tar.bz2 geckodriver-v0.21.0-linux64.tar.gz

# Get recent version of chromedriver
RUN sudo wget --quiet https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip \
  && sudo unzip chromedriver_linux64.zip \
  && sudo mv $PWD/chromedriver /usr/local/bin \
  && sudo rm -f chromedriver_linux64.zip


# start xvfb automatically to avoid needing to express in circle.yml
ENV DISPLAY :99
RUN printf '#!/bin/sh\nXvfb :99 -screen 0 1280x1024x24 &\nexec "$@"\n' > /tmp/entrypoint \
  && chmod +x /tmp/entrypoint \
        && sudo mv /tmp/entrypoint /docker-entrypoint.sh

COPY tools/uglifyjs-pathfix /usr/local/bin/uglifyjs

# ensure that the build agent doesn't override the entrypoint
LABEL com.circleci.preserve-entrypoint=true

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/bin/sh"]
WORKDIR /src
