# Exemples discussion-helper

Un livre de recettes des usages courants. Chaque bloc Python tourne avec **rien
d'installé au-delà du paquet de base** — pas de micro, pas de modèle, pas de
carte son — parce que les parties sont des protocoles et que
`discussion_helper.testing` fournit un faux connu-bon de chacune. Collez
n'importe lequel dans un fichier et regardez-le marcher.

Ce n'est pas une commodité de test, c'est le propos. Le comportement le plus
difficile à obtenir dans un agent vocal est aussi le plus difficile à observer
dans une pièce : l'audio s'est-il vraiment arrêté, ce qui était en file a-t-il
été jeté ou joué en douce, le tour de parole est-il revenu.

- [1. La boucle, sans rien derrière](#1-la-boucle-sans-rien-derrière)
- [2. Couper la parole à l'agent](#2-couper-la-parole-à-lagent)
- [3. Prouver que l'audio en file a été jeté](#3-prouver-que-laudio-en-file-a-été-jeté)
- [4. Lire la décomposition de latence](#4-lire-la-décomposition-de-latence)
- [5. Plafonner la réponse](#5-plafonner-la-réponse)
- [6. Semi-duplex strict](#6-semi-duplex-strict)
- [7. Le délai de grâce et l'écho](#7-le-délai-de-grâce-et-lécho)
- [8. Finir sur le silence](#8-finir-sur-le-silence)
- [9. Apporter sa propre partie](#9-apporter-sa-propre-partie)
- [10. En vrai : micro, modèle, voix](#10-en-vrai--micro-modèle-voix)
- [11. Ligne de commande](#11-ligne-de-commande)
- [12. HTTP et un agent qui peut interrompre](#12-http-et-un-agent-qui-peut-interrompre)

## 1. La boucle, sans rien derrière

Écouter, répondre, parler, recommencer. `Conversation` revient en portant ce
qui a été dit, l'état de tour de parole sur lequel elle s'est terminée ainsi que
les temps.

```python
import asyncio

from discussion_helper import Discussion, Floor
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    talk = Discussion(ScriptedListener(["bonjour", "ça va ?"]), EchoResponder(), SilentVoice())
    conversation = await talk.run()
    for u in conversation.utterances:
        print(f"{u.speaker}: {u.text}")
    print("ended on:", conversation.floor)


asyncio.run(main())
# user: bonjour
# agent: bonjour
# user: ça va ?
# agent: ça va ?
# ended on: Floor.IDLE
```

`Floor.IDLE` à la fin compte davantage qu'il n'y paraît : un agent qui tient
encore le tour de parole est un agent à qui personne ne peut répondre.

## 2. Couper la parole à l'agent

Le comportement pour lequel tout le paquet existe. `interrupt_after_s` met en
scène une interruption à cette distance dans la réponse de l'agent.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.05),
        EchoResponder(sentences=5),
        SilentVoice(seconds_per_sentence=1.0),
        Policy(barge_in_grace_s=0.0),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)
    print("interruption rate:", conversation.interruption_rate)


asyncio.run(main())
# interrupted: True
# interruption rate: 1.0
```

`barge_in_grace_s=0.0` n'est juste que dans un test. Voir l'exemple 7.

Le **taux d'interruption** est un diagnostic qui mérite d'être surveillé en
production : un taux élevé signifie d'ordinaire des réponses trop longues, ce
qu'une transcription ne montrera jamais, puisque le texte d'une réponse
interrompue a l'air complet.

## 3. Prouver que l'audio en file a été jeté

Une réponse est synthétisée en avance de la lecture : une interruption trouve
donc toujours de l'audio fabriqué et pas encore entendu. Le jouer quand même —
parce qu'il existe, parce qu'il a été payé — est ce qui donne à un agent l'air
d'être sourd.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice(seconds_per_sentence=1.0)
    await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.05),
        EchoResponder(sentences=5),
        voice,
        Policy(barge_in_grace_s=0.0),
    ).run()
    print("started:", len(voice.spoken))  # of 5
    print("completed:", voice.completed)  # the cut one does not count
    print("stops:", voice.stops)


asyncio.run(main())
# started: 1
# completed: []
# stops: 1
```

Deux assertions en une : les phrases qui suivent l'interruption ne commencent
jamais ; la phrase coupée n'est **pas** comptée comme dite. Si `completed`
portait la phrase coupée, chaque transcription prétendrait que l'utilisateur a
entendu quelque chose qu'il n'a pas entendu.

## 4. Lire la décomposition de latence

Par échange, pas en total — un chiffre unique dit qu'une conversation paraît
lente et rien sur le pourquoi.

```python
import asyncio

from discussion_helper import Discussion
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"]),
        EchoResponder(delay_s=0.05),
        SilentVoice(seconds_per_sentence=0.40, first_audio_s=0.02),
    ).run()
    timing = conversation.timings[0]
    print("slowest stage:", timing.slowest_stage)
    print("to first audio:", round(timing.to_first_audio_s, 3), "s")
    print("speak:", round(timing.speak_s, 3), "s")
    print(timing.as_dict())


asyncio.run(main())
# slowest stage: think
# to first audio: 0.072 s
# speak: 0.02 s
# {'endpoint_s': 0.0, 'recognise_s': 0.0, 'think_s': 0.052, 'speak_s': 0.02,
#  'to_first_audio_s': 0.072, 'slowest_stage': 'think'}
```

Ce sont des durées mesurées : le dernier chiffre bouge d'une exécution à
l'autre — `think_s` tombe un cheveu au-dessus des 0,05 demandées au faux. Ce
qui est stable, c'est la forme : quelle étape est la plus lente, puis la
répartition ci-dessous.

Notez que `speak_s` vaut **0,02** et non 0,40 : il mesure le silence avant le
son, pas la lecture. Confondez les deux et un moteur rapide lisant une longue
phrase paraît plus lent qu'un moteur lent lisant une phrase courte — la seule
erreur de mesure qui rende un budget de latence inutile.

`as_dict()` rend les six mêmes champs que le `--json` de la ligne de commande
et que le flux d'événements HTTP : un lecteur obtient la même décomposition par
quelque porte qu'il soit entré.

## 5. Plafonner la réponse

Un agent qui parle quatre-vingt-dix secondes est un agent que l'utilisateur
*doit* interrompre. Le correctif de latence le moins cher est d'ordinaire une
réponse plus courte, pas un modèle plus rapide.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice()
    await Discussion(
        ScriptedListener(["bonjour"]),
        EchoResponder(sentences=10),
        voice,
        Policy(max_reply_sentences=2),
    ).run()
    print("sentences spoken:", len(voice.spoken))


asyncio.run(main())
# sentences spoken: 2
```

## 6. Semi-duplex strict

Brutal mais juste sur un haut-parleur sans annulation d'écho acoustique. Sans
cela, la propre voix de l'agent atteignant son propre micro ressemble
exactement à l'utilisateur qui parle : chaque réponse s'interrompt donc
elle-même au bout d'une syllabe.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    voice = SilentVoice(seconds_per_sentence=0.02)
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        voice,
        Policy(allow_barge_in=False),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)
    print("completed:", len(voice.completed))


asyncio.run(main())
# interrupted: False
# completed: 3
```

## 7. Le délai de grâce et l'écho

Le juste milieu, celui par défaut. Une interruption arrivant dans la fenêtre de
grâce est traitée comme la première syllabe de l'agent lui-même plutôt que
comme l'utilisateur.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], interrupt_after_s=0.0),
        EchoResponder(sentences=3),
        SilentVoice(seconds_per_sentence=0.05),
        Policy(barge_in_grace_s=0.5),
    ).run()
    agent = [u for u in conversation.utterances if u.speaker == "agent"][0]
    print("interrupted:", agent.interrupted)


asyncio.run(main())
# interrupted: False
```

Point crucial : le guetteur continue de guetter au lieu de rendre la main, sans
quoi un seul écho désactiverait l'interruption pour tout le reste du tour.
Montez-le sur un haut-parleur, baissez-le sur un casque ; 350 ms est le défaut.
C'est un compromis, pas un correctif — l'annulation d'écho est la vraie réponse.

## 8. Finir sur le silence

Un micro ouvert dans une pièce vide est une fin ordinaire, pas une erreur.

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    conversation = await Discussion(
        ScriptedListener(["bonjour"], pace_s=5.0),
        EchoResponder(),
        SilentVoice(),
        Policy(silence_timeout_s=0.05),
    ).run()
    print("utterances:", conversation.utterances)


asyncio.run(main())
# utterances: []
```

Utilisez `async with` quand vous voulez que les trois parties soient libérées
en sortant — un micro laissé ouvert survit au programme qui l'a ouvert :

```python
import asyncio

from discussion_helper import Discussion
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice


async def main():
    listener, responder, voice = ScriptedListener([]), EchoResponder(), SilentVoice()
    async with Discussion(listener, responder, voice):
        pass
    print(listener.closed, responder.closed, voice.closed)


asyncio.run(main())
# True True True
```

## 9. Apporter sa propre partie

`Listener`, `Responder` et `Voice` sont des protocoles **structurels** — aucune
classe de base à hériter, aucun enregistrement. Un recogniseur dans le nuage,
un modèle scripté pour une démonstration, une ligne téléphonique au lieu d'un
haut-parleur : chacun est une classe, la boucle ne changeant pas.

```python
import asyncio
from collections.abc import AsyncIterator

from discussion_helper import Discussion, Responder
from discussion_helper.testing import ScriptedListener, SilentVoice


class RuleBasedResponder:
    """Answers without a model at all."""

    def __init__(self) -> None:
        self.closed = False

    async def reply(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        heard = messages[-1]["content"].lower()
        yield "Bonsoir." if "soir" in heard else "Bonjour."

    async def stop(self) -> None:
        pass

    async def aclose(self) -> None:
        self.closed = True


async def main():
    print("conforms:", isinstance(RuleBasedResponder(), Responder))
    voice = SilentVoice()
    await Discussion(ScriptedListener(["bonsoir"]), RuleBasedResponder(), voice).run()
    print(voice.spoken)


asyncio.run(main())
# conforms: True
# ['Bonsoir.']
```

La seule méthode à ne pas rater est `Voice.stop()` : elle doit **jeter** ce qui
a été synthétisé et pas encore entendu, jamais l'écouler. L'exemple 3 est le
test de cela.

## 10. En vrai : micro, modèle, voix

Demande le matériel et les paquets frères : celui-ci ne tourne donc pas sur une
installation nue.

```bash
pip install 'discussion-helper[all]'
```

```python
import asyncio

from discussion_helper import Discussion, Policy
from discussion_helper.adapters import LocalResponder, SpeakerVoice, VocalListener


async def main():
    async with Discussion(
        VocalListener(language="fr"),
        LocalResponder(),
        SpeakerVoice(voice="ff_siwis", language="fr"),
        Policy(barge_in_grace_s=0.35, max_reply_sentences=3),
    ) as talk:
        conversation = await talk.run()
    print(conversation.interruption_rate)


asyncio.run(main())
```

Chaque adaptateur importe son frère **à l'intérieur** de la méthode qui en a
besoin : une installation de base porte donc la boucle et rien d'autre — et un
extra manquant lève un message qui nomme la commande d'installation plutôt
qu'une `ImportError` sur un paquet dont vous n'avez jamais entendu parler.

`VocalListener` construit un vrai `vocal_helper.Pipeline` (détection d'activité
vocale, puis reconnaissance) pour la transcription, puis lit séparément le début
de parole sur les trames brutes. Ce sont deux questions différentes avec deux
échéances différentes : une interruption qui aurait attendu une transcription
arriverait une seconde trop tard ; d'ici là l'agent parle par-dessus
quelqu'un depuis une phrase entière. `onset_rms` règle le détecteur de début
pour une pièce bruyante.

## 11. Ligne de commande

```bash
# The loop, with no hardware. Start here.
discussion-helper rehearse 'bonjour' 'ça va ?'

# Stage an interruption 200 ms into a five-sentence reply.
discussion-helper rehearse 'bonjour' --sentences 5 --interrupt-after 0.2

# The microphone.
discussion-helper talk --voice ff_siwis --language fr
discussion-helper talk --no-barge-in          # strict half-duplex
discussion-helper talk --json                 # machine-readable
```

Toutes les options des deux commandes sont dans
`skills/discussion-helper/references/cli-reference.md`.

## 12. HTTP et un agent qui peut interrompre

```bash
pip install 'discussion-helper[server]'
python -m discussion_helper.api        # 127.0.0.1:8000, docs at /docs
```

```bash
curl -X POST localhost:8000/sessions
curl localhost:8000/sessions/{id}/events      # transcript, floor and timings as they grow
curl -X POST localhost:8000/sessions/{id}/interrupt
curl -X DELETE localhost:8000/sessions/{id}
```

`POST /turn` prend un seul tour sous forme de texte : c'est la seule façon de
demander directement quelque chose au modèle de la conversation.

Avec `[mcp]` installé, `discussion-helper-mcp` republie ces mêmes routes comme
outils d'agent — une seule implémentation, si bien que les deux surfaces ne
peuvent pas dériver vers un désaccord. Un agent ne peut pas *tenir* une
conversation (il n'a pas d'oreilles), mais il peut en démarrer une, la
surveiller, prendre un tour et l'**interrompre**. C'est cette dernière capacité
qui justifie la surface : « arrête de parler » est une chose que les gens
disent à un agent ; la faire passer par le même `Voice.stop` que
l'interruption du micro signifie qu'elle s'arrête de la même façon — en jetant
ce qui a été synthétisé plutôt qu'en le laissant s'écouler.
