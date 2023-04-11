#!/usr/bin/env python3
"""
Get the current versions of Chrome and Firefox to aid in tagging Docker images.

Old Docker image tag: 20230411-chromelatest-firefoxlatest
New Docker image tag: 20230411-chrome112-firefox112-py311
"""
from datetime import date
from sys import version_info

import requests


def latest_version_of_chrome() -> str:
    URL = "https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
    return requests.get(URL).text.split(".")[0]


def latest_version_of_firefox() -> str:
    URL = "https://www.mozilla.org/en-US/firefox/releasenotes"
    return requests.get(URL, allow_redirects=True).url.split("/")[-3].split(".")[0]


def docker_image_tag() -> str:
    """
    Return 20230411-chrome112-firefox112-py311
    """
    chrome = f"chrome{latest_version_of_chrome()}"
    firefox = f"firefox{latest_version_of_firefox()}"
    python = "py{}{}".format(*version_info)
    return f"{date.today():%Y%m%d}-{chrome}-{firefox}-{python}"


if __name__ == "__main__":
    print(latest_version_of_chrome())
    print(latest_version_of_firefox())
    print(docker_image_tag())
