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
    "This is <strong>unreleased documentation for Pyodide next version</strong>. " +
    "For up-to-date documentation, see <a href='/en/stable/'>the stable version</a>." +
    "</p>";
  warning.querySelector('a').href = window.location.pathname.replace('/latest', '/stable');

  var parent = document.getElementById("main-content").firstChild;
  while(parent != null && parent.nodeType == 3){ // skip TextNodes
    parent = parent.nextSibling;
  }
  parent.insertBefore(warning, parent.firstChild);
}

document.addEventListener('DOMContentLoaded', warnOnLatestVersion);