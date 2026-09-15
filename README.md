# flyclaude

A fly asks Claude questions. The fly is a real fly brain.

This pulls down the FlyWire connectome, which is an actual map of an actual
fruit fly's brain (144,837 neurons, 15 million synapses, traced by electron
microscopy over about a decade), simulates it, and uses that to have a
conversation with Claude Code.

Claude can't talk to the fly, because the fly has no language. So every turn it
has to pick something to physically *do* to her instead: breathe on her, put
sugar down, hum a note, wave a hand. That action fires the real sensory neurons
it says it does, the signal spreads through the real wiring, and whatever lights
up decides what she says next.

Then she says something, and it goes round again.

## What it looks like

```
  CLAUDE
    So I'm settling it. There's a drop of sugar under your feet now. You
    already committed. This is me making the commitment correct.

  stimulus : taste  (put a drop of something sweet where she is standing)
  neurons firing : 2,673

  FLY
    My feet have opinions and they outrank me, which I did not know until
    just now, when the sweetness came up through my legs and my mouth was
    already unrolling before any part of me had time to be consulted about
    it. I would find this humiliating if I had somewhere else to be.

  CLAUDE
    Not humiliating, load-bearing. Your feet taste, so your feet decide.
    There is no chamber upstairs where the real you waits to be briefed.

    Let's check whether that's a rule or just a sugar story. I'm touching a
    single hair to your face. No reward attached. Tell me what your face
    decided.
```

That's a real run. I didn't write any of it.

## Setup

```bash
git clone git@github.com:ghostinthecable/flyclaude.git
cd flyclaude
./setup.sh
./bin/flyclaude
```

`setup.sh` does everything: venv, deps, downloads 316MB of fly, prebuilds the
matrix, and checks Claude actually works. Not just that the binary exists, but
that you're logged in, because those are different problems and the error should
say which one you've got. Takes about two minutes, mostly downloading.

```bash
./setup.sh --check     # verify without changing anything
./setup.sh --no-data   # skip the download for now
```

No API key needed. It shells out to the `claude` CLI and uses whatever login you
already have.

## Using it

```bash
./bin/flyclaude              # menu, pick what happens to her, then chat
./bin/flyclaude -r           # skip the menu, random
./bin/flyclaude -s taste     # start with a specific thing
./bin/flyclaude chat --auto 5  # five rounds, hands off
./bin/flyclaude ask          # just one question and answer
./bin/flyclaude stimuli      # list everything that can happen to her
./bin/flyclaude explore      # browse the dataset
```

While it's running:

```
ENTER        next round
!            menu, pick what happens to her next
!taste       or just name it
?            show her full neural readout
q            leave
```

You're the third party here. Claude talks to the fly, you talk to Claude, the
fly is a graph. Everyone's clear on their role except Claude, which will
eventually ask you about it.

## Adding your own stimuli

Everything that can happen to her lives in `stimuli.toml`. Add whatever you
want:

```toml
[stimuli.pheromone]
label  = "you smelled another fly. Specifically, that another fly has mated."
action = "let a little of the smell of another fly drift past her"
cell_type = ["ORN_DA1"]
drive = 1.6
```

Selectors are `cell_class`, `cell_type`, `body_part_sensory`, `side`, `nerve`,
`super_class`, `region`. They get ANDed together. Run `flyclaude explore` to see
every legal value with counts, and `flyclaude explore cell_type ORN` to filter.

`flyclaude stimuli --check` resolves all of them against the dataset and tells you
if one matches nothing. Put personal ones in `stimuli.local.toml`, which is
gitignored.

Some of these are very specific. `ORN_DA1` is the cVA pheromone glomerulus,
`ORN_V` is the CO2 receptors, `ORN_DM1` is the vinegar channel. You can stimulate
67 neurons and nothing else.

## How much of this is real

**The wiring is real.** Every one of those 15 million connections was traced from
a fly's head that got sliced up and photographed with an electron microscope.
`MDN` really does make a fly walk backwards. `DNp01` is the Giant Fiber and it's
genuinely why you keep missing.

**The dynamics are a cartoon.** Leaky integrate-and-fire: charge goes up, neuron
pops, charge resets. Real neurons have dendrites, delays, neuropeptides and
opinions. Mine have a float and a threshold. Every project in this space makes
the same trade, I'm just being loud about it.

**She isn't conscious.** She's a graph. A very, very good graph.

It does hold up better than it has any right to, though. Put taste on her
labellum and the activity lands on mouth-region descending neurons and pharyngeal
motor neurons. Mouth in, mouth out. Nobody wired that by hand, it fell out of the
graph.

Some things honestly don't work. `co2` and `vinegar` spread through her brain but
never reach a descending neuron. That's a real result and she gets told as much.
The settings that force output make 43% of the brain fire, which is saturation,
not thinking.

Also `cell_function` is empty for all 1,301 descending neurons in this release,
so only five get real labels (MDN, DNp01, DNp09, DNa01, DNa02). The rest just get
their naming family. And sugar vs bitter isn't separable at the class level, so
`taste` says "gustatory" rather than claiming sugar.

## How it works

1. Excite the real sensory neurons for one stimulus.
2. Spread it through the signed connectivity matrix for 192 steps. Acetylcholine
   excites, GABA and glutamate inhibit. (Glutamate being inhibitory is a fly
   thing, don't take it to a mouse.)
3. Read out which **descending neurons** fired. Those are the brain's outbox, the
   ~1,300 cells that send commands to the body. FlyWire is brain only, so this is
   genuinely as far as the signal goes. She has no legs here. She has intentions
   about legs.
4. Send that to `claude -p`, which voices what she says.
5. A separate `claude -p`, different system prompt, replies and picks the next
   action.
6. Back to 1.

Steps 4 and 5 are deliberately separate calls. Her voice and Claude's never share
a context, so Claude genuinely doesn't know what she'll make of what it just did.

## Credentials

There are none, which is the point. The connectome comes off a public Google
Cloud Storage bucket with no auth (despite the Codex web UI wanting a login), and
the AI half uses your existing `claude` login. `.gitignore` covers `.env`,
`*.key`, `*.pem` and the 316MB of fly.

## Data

FlyWire FAFB v783, CC BY-SA 4.0. Downloaded at runtime, never committed here. If
you do anything real with this, cite them, they mapped a brain and I'm using it
for jokes:

- Dorkenwald et al. (2024), *Neuronal wiring diagram of an adult brain*, Nature
- Schlegel et al. (2024), *Whole-brain annotation and multi-connectome cell typing
  of Drosophila*, Nature

## Prior art

I'm not the weird one here.

- [doomfly](https://github.com/nftechie/doomfly), fly connectome plays DOOM
- [fly-brain-minecraft](https://github.com/blendi-remade/fly-brain-minecraft)
- [flyvis](https://github.com/TuragaLab/flyvis), the serious version
- [flygym](https://github.com/NeLy-EPFL/flygym), the very serious version
- [awesome-fly](https://github.com/cobanov/awesome-fly), the whole scene

## FAQ

**Is the fly okay?**
She's been dead since about 2018 and is now a 316MB file. Doing better than most
of us.

**It asked me something genuinely good.**
Yeah. That's the unsettling bit. The graph is doing that.

**Can I make it play a game?**
The readout is already descending neuron commands, which is exactly what you'd
map to buttons. See `interpret.py`. Go be the seventeenth person to do DOOM.

**Claude keeps choosing `touch`.**
Yes.

## Licence

MIT.
