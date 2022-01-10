"use strict";

// Source:
// https://github.com/anymail/django-anymail/blob/4c443f5515d1d5269a95cb54cf75057c56a3b150/docs/_static/version-alert.js

function warnOnLatestVersion() {

  // The warning text and link is really specific to RTD hosting,
  // so we can just check their global to determine version:
  if (!window.READTHEDOCS_DATA || window.READTHEDOCS_DATA.version !== "latest") {
    return;  // not latest, or not on RTD
  }

  var warning = document.createElement('div');
  warning.setAttribute('class', 'admonition danger');
  warning.innerHTML = "<p class='first admonition-title'>Note</p> " +
    "<p class='last'> " +
    "This document is for an <strong>unreleased development version</strong>. " +
    "Documentation is available for the <a href='/en/stable/'>current stable release</a>, " +
    "or for older versions through the &ldquo;v:&rdquo; menu at bottom left." +
    "</p>";
  warning.querySelector('a').href = window.location.pathname.replace('/latest', '/stable');

  var parent = document.querySelector('div.body')
    || document.querySelector('div.document')
    || document.body;
  parent.insertBefore(warning, parent.firstChild);
}

document.addEventListener('DOMContentLoaded', warnOnLatestVersion);