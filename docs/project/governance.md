# pyodide governance and decision-making

The purpose of this document is to formalize the governance process used by the
pyodide project, to clarify how decisions are made and how the various
members of our community interact.
This document establishes a decision-making structure that takes into account
feedback from all members of the community and strives to find consensus, while
avoiding any deadlocks.

Anyone with an
interest in the project can join the community, contribute to the project
design and participate in the decision making process. This document describes
how to participate and earn merit in the pyodide community.

## Roles And Responsibilities

### Contributors

Contributors are community members who contribute in concrete ways to the
project. Anyone can become a contributor, and contributions can take many forms
– not only code – as detailed in the {ref}`how_to_contibute`.

### Community members team

The community members team is composed of community members who have permission on
Github to label and close issues. Their work is
crucial to improve the communication in the project.

After participating in pyodide development with pull requests and reviews for a period of time, any contributor may become a member of the team.
The process for adding team members is modeled on the [CPython project](
https://devguide.python.org/triaging/#becoming-a-member-of-the-python-triage-team).
Any core developer is welcome to propose a pyodide contributor to join the
community members team. Other core developers are then consulted: while it is expected
that most acceptances will be unanimous, a two-thirds majority is enough.

### Core developers

Core developers are community members who have shown that they are dedicated to
the continued development of the project through ongoing engagement with the
community. They have shown they can be trusted to maintain pyodide with
care. Being a core developer allows contributors to more easily carry on
with their project related activities by giving them direct access to the
project’s repository and is represented as being a member of the core team on the
pyodide [GitHub organization](https://github.com/orgs/pyodide/teams/core/members).
Core developers are expected to review code
contributions, can merge approved pull requests, can cast votes for and against
merging a pull-request, and can be involved in deciding major changes to the
API.

New core developers can be nominated by any existing core developers. Once they
have been nominated, there will be a vote by the current core developers.
Voting on new core developers is one of the few activities that takes place on
the project's private communication channels. While it is expected that most votes
will be unanimous, a two-thirds majority of the cast votes is enough. The vote
needs to be open for at least 1 week.

Core developers that have not contributed to the project (commits or GitHub
comments) in the past 2 years will be asked if they want to become emeritus
core developers and recant their commit and voting rights until they become
active again.


## Decision Making Process

Decisions about the future of the project are made through discussion with all
members of the community. All non-sensitive project management discussion takes
place on the project contributors' [issue
tracker](https://github.com/pyodide/pyodide/issues) and on [Github
discussion](https://github.com/pyodide/pyodide/discussions).
Occasionally, sensitive discussion occurs on a private communication channels.

pyodide uses a "consensus seeking" process for making decisions. The group
tries to find a resolution that has no open objections among core developers.
At any point during the discussion, any core-developer can call for a vote,
which will conclude two weeks from the call for the vote. This is what we
hereafter may refer to as “the decision making process”.

Decisions (in addition to adding core developers as above)
are made according to the following rules:

* **Minor Documentation changes and minor build setup changes**, include for
  instance improving the wording in the documentation, updating CI or
  dependencies.  Core developers are expected to give “reasonable time” to
  others to give their opinion on the pull request if they’re not confident
  others would agree. If no review is received within this time, the Pull
  Request can be merged.

* **Code changes impacting user facing APIs, or having backward compatibility
  implications** require a review and an approval (+1 vote) by a core
  developer, no objections with -1 vote by a core developer (lazy consensus).
  This process happens on the pull-request page.

* **Changes to the governance model** use the same decision process outlined
  above.
