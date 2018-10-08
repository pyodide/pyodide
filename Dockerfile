FROM circleci/python:3.7.0-stretch-browsers

# We need at least g++-8, but stretch comes with g++-6
# Set up the Debian testing repo, and then install g++ from there...
RUN sudo bash -c "echo \"deb http://ftp.us.debian.org/debian testing main contrib non-free\" >> /etc/apt/sources.list"
RUN sudo apt-get update
RUN sudo apt-get install node-less cmake build-essential clang-format-6.0 uglifyjs chromium ccache
RUN sudo apt-get install -t testing g++-8
RUN sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-6 60 --slave /usr/bin/g++ g++ /usr/bin/g++-6
RUN sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-8 80 --slave /usr/bin/g++ g++ /usr/bin/g++-8
RUN sudo update-alternatives --set gcc /usr/bin/gcc-8
RUN sudo apt-get clean
RUN sudo ln -s /usr/bin/clang-format-6.0 /usr/bin/clang-format

RUN sudo pip install pytest pytest-xdist pytest-instafail selenium PyYAML flake8

# Get recent version of Firefox and geckodriver
RUN sudo wget --quiet -O firefox.tar.bz2 https://download.mozilla.org/\?product\=firefox-latest-ssl\&os\=linux64\&lang\=en-US
RUN sudo tar jxf firefox.tar.bz2
RUN sudo rm -f /usr/local/bin/firefox
RUN sudo ln -s $PWD/firefox/firefox /usr/local/bin/firefox
RUN sudo wget --quiet https://github.com/mozilla/geckodriver/releases/download/v0.21.0/geckodriver-v0.21.0-linux64.tar.gz
RUN sudo tar zxf geckodriver-v0.21.0-linux64.tar.gz -C /usr/local/bin

# Get recent version of chromedriver
RUN sudo wget --quiet https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip
RUN sudo unzip chromedriver_linux64.zip
RUN sudo mv $PWD/chromedriver /usr/local/bin

RUN sudo bash -c "echo 'application/wasm wasm' >> /etc/mime.types"

WORKDIR /src
