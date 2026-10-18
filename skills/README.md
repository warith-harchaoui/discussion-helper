# discussion-helper as an agent skill

`skills/discussion-helper/` packages this toolbox as a **Claude Skill** and an
**OpenCode skill** — both read the same `SKILL.md` (YAML frontmatter + Markdown
body + progressive-disclosure `references/`).

The skill leads with `discussion-helper rehearse`, deliberately. An agent
helping somebody debug a voice loop should reach for the thing that needs no
hardware first; the room is the slowest possible way to test a state machine.

## Layout

```
skills/discussion-helper/
├── SKILL.md                 # name + trigger-rich description + instructions
└── references/
    └── triggers.md          # when this is the answer, and when it is not
```

## Installing

```bash
cp -r skills/discussion-helper ~/.claude/skills/          # Claude Code
cp -r skills/discussion-helper ~/.config/opencode/skills/ # OpenCode
```
