#! /usr/bin/env python3

def open(url, new=0, autoraise=True):
    from js import window
    window.open(url, "_blank")

def open_new(url):
    return open(url, 1)

def open_new_tab(url):
    return open(url, 2)
