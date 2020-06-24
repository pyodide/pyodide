FROM circleci/python:3.7.7-buster

RUN sudo apt-get update \
  # bzip2 and libgconf-2-4 are necessary for extracting firefox and running chrome, respectively
  && sudo apt-get install bzip2 libgconf-2-4 node-less cmake build-essential clang-format-6.0 \
                  uglifyjs chromium ccache libncurses6 gfortran f2c swig g++-8 \
  && sudo apt-get clean \
  && sudo apt-get autoremove \
  && test "Comment: Hardcode nodejs path for uglifyjs, so it doesn't conflict with emcc's nodejs" \
  && test $(which node) = /usr/bin/node && test $(which uglifyjs) = /usr/bin/uglifyjs \
  && echo '#!/bin/sh -e\nexec /usr/bin/node /usr/bin/uglifyjs "$@"' >/tmp/uglifyjs \
  && chmod a+x /tmp/uglifyjs && sudo mv -t /usr/local/bin /tmp/uglifyjs

RUN sudo pip install pytest pytest-xdist pytest-instafail pytest-rerunfailures selenium PyYAML flake8 \
    && sudo rm -rf /root/.cache/pip

# Get recent version of Firefox and geckodriver
RUN sudo wget --quiet -O firefox.tar.bz2 https://ftp.mozilla.org/pub/firefox/releases/63.0.1/linux-x86_64/en-US/firefox-63.0.1.tar.bz2 \
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

# ensure that the build agent doesn't override the entrypoint
LABEL com.circleci.preserve-entrypoint=true

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/bin/sh"]
WORKDIR /src
