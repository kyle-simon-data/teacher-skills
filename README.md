# Teacher Skills

[Agent Skills](https://agentskills.io) for classroom work: ready-made instructions and scripts that teach an AI assistant to handle teaching tasks the same way every time.

Built by Kyle Simon for his teaching at Red Lion Area School District.

## Skills

| Skill | What it does |
|---|---|
| [LinkIt Exam View Converter](skills/linkit-examview-converter) | Turns an existing test and answer key into a file LinkIt! imports with the Exam View button, plus a spreadsheet of anything that needs manual entry |
| [Guided Notes Builder](skills/guided-notes-builder) | Turns lesson slides into a print-ready student guided-notes packet and matching teacher key (Word and PDF), optionally checked against the unit test |

More skills are on the way.

## Installing a skill

Each folder under `skills/` is a complete, self-contained skill. Install only the ones you want.

**Claude (web, desktop or mobile):** download the skill's folder and zip it, keeping its original folder name (for example `linkit-examview-converter`). Then go to **Customize → Skills**, click **+**, choose **Create skill → Upload a skill**, and select the zip. Code execution must be turned on in your settings.

**Claude Code:** copy the skill's folder into `~/.claude/skills/` (for you) or `.claude/skills/` (for one project).

**Other tools:** any AI tool that supports the Agent Skills format can use a skill folder as is.

Each skill's own README explains how to use it.

## Repository layout

```text
skills/
  <skill-name>/
    SKILL.md        instructions the AI follows
    README.md       what the skill does and how to use it
    scripts/        helper scripts, if any
    references/     detailed reference material, if any
    examples/       sample inputs, if any
    tests/          automated tests, if any
```

## Feedback

Found a problem or have an idea? Open an issue. If a skill's behavior depends on an outside platform, like LinkIt, please include what you uploaded and what happened.

## License

MIT. See [LICENSE](LICENSE).

These skills are independent projects and are not affiliated with or endorsed by the platforms they work with. Product names belong to their owners.
