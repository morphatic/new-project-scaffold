# New Project Checklist

This document captures a full list of all of the elements of a typical project that I might start. It documents all of the steps I would normally go through to setup and maintain a project. The goal of creating this checklist is to automate these steps so that I can turn them into appropriate AI tools, hooks, or skills.

In the interests of doing a brain dump, I'm just going to start listing things. I'll organize this better later.

* `cspell.json` and some sort of skill or hook to automate running `cspell` at appropriate times/intervals
* `.editorconfig` that should be minimal, follow most common conventions but tailored to my preferences where there are multiple common ways that a thing gets done in common use.
* `.markdownlint.json` with appropriate (possibly customized) rules, and a skill/hook to ensure any Markdown files in the project conform
* Linters: ALL code-based projects must be linted with an appropriate linter and 100% compliant with linting rules, unless configured otherwise in the project. Deviations from the most common conventions for a given language should be rare and ALWAYS discussed with me before being added to the config
* Coding guidelines: along with linting, every project should have a skill or guideline document capturing best practices, do's and don'ts, etc. for that language. These should be designed specifically and intentionally to be consumed and rigorously followed by agents
* Permissions: all projects should have a config file for agents that pre-assigns permissions for all non-destructive commands in a way designed to minimize the amount of babysitting I'll have to do for a project and maximize the amount of time that agents can work autonomously. Rules that cannot be captured in standard permissions should be implemented as hooks.
* `docs/` is (for now) a folder that I will include in every project designed to contain brainstorming, planning, research, background, and other artifacts that capture and provide a solid and consistent context for agents working on the project. Since the name `docs/` is likely to have a collision with some other system at some point, and could be confused for end-user-facing documentation, I'm open to another name for this folder, e.g. `knowledge/`, `bok/`, `resources/`, `background/`, `meta/`, or something like that. Whatever name I choose, I'd like it to be stable and consistent across projects from here on out. Ideally this would be a name that could easily be adopted by a community of practice, were I ever to propose it
* `git init` and appropriate default `.gitignore`. Since we won't always know what language(s) or framework(s) we'll be using at the time a project is started, the default has to cover things we *can* know ahead of time, and there should be a skill or hook that proactively keeps this up to date as new components are added to the project.

Here are some characteristics of what my ideal projects would be like by default. The idea is that I don't want to have to explain these things to my agentic partner(s) every time, and get right into doing the actual intellectual work of the project.

* There should be "to do" list that is ALWAYS up to date and should generally be instantly accessible without the agent have to clutter up and consume the context to regenerate it each time I ask "what's next?" I realize that scanning the project's memories and recent history will be necessary at times to maintain the list, but I really want to minimize the amount of tokens required to do this.
* Coding agents should spawn sub-agents proactively with their own contexts to minimize polluting the top-level manager agent's context and allow sessions to go longer before requiring compaction or clearing
* The spec is the bible of the project. The very first thing that needs to get done after initializing a new project is generating a comprehensive spec with no gaps.

Questions: these are things about which I'm unsure or undecided.

1. Should we adopt the GSD framework as part of our default project setup? It's [documented here](https://github.com/gsd-build/get-shit-done). It appears to cover a lot of the issues I've raised above, and possibly a lot more that I haven't thought of.
2. Use [NLSpec](https://github.com/jhugman/nlspec) or the [prodkit feature-spec interview skill](https://github.com/ramybarsoum/prodkit/blob/main/skills/feature-spec-interview/SKILL.md)? I have used NLSpec on 4-5 projects so far and it has been AMAZING at helping me successfully generate production ready projects. The feature-spec interview skill looks like a more structured way to approach NLSpec generation than I've been following. To date, I've just given a general description of the kind of project I want to build in claude code, pointed CC at the NLSpec spec and told it to generate an appropriate NLSpec document that follows the format. Once it's generated, I will read through it and make edits/changes where appropriate and then tell CC to start building the project following the spec. I'm wondering if I should keep doing that, try out the prodkit approach, or possibly combine them?
3. I need to generate a set of default hooks for handling permissions that can't be handled by "allow" rules in settings. For example, I frequently am asked to approve commands like `cd some/path && ls -la` when I've already got `Bash(ls)` in my allow list because of the compound command `&&`. I'm not sure how many such hooks I'll need, but there's a log of ALL of my Bash tool uses in `../permissions-mastery/bash_commands.json` that were extracted from my session logs.

Some documents that will be helpful in helping us generate our new projects setup script:

* `project-setup-automation-confo.md`
* `../claude-code-permissions-mastery.md`
* `../interrogating-cc-logs.md`
