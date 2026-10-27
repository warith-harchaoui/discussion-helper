# Exemples discussion-helper

Un livre de recettes des usages courants. Les sections 1 à 9 tournent avec
**rien d'installé au-delà du paquet de base** — pas de micro, pas de modèle,
pas de carte son — parce que les parties sont des protocoles et que
`discussion_helper.testing` fournit un faux connu-bon de chacune. Collez
n'importe lequel dans un fichier et regardez-le marcher. Les deux suivantes
réclament le vrai matériel ; elles le disent là où elles commencent.

Ce n'est pas une commodité de test, c'est le propos. Le comportement le plus
difficile à obtenir dans un agent vocal est aussi le plus difficile à observer
dans une pièce : l'audio s'est-il vraiment arrêté, ce qui était en file a-t-il
été jeté ou joué en douce, le tour de parole est-il revenu.

## Table des matières

- [Mise en place](#mise-en-place)
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
- [11. HTTP et un agent qui peut interrompre](#11-http-et-un-agent-qui-peut-interrompre)
- [Ligne de commande](#ligne-de-commande)
- [Dépannage](#dépannage)

## Mise en place

Les sections 1 à 9 ne demandent rien de plus que le paquet de base :

```bash
pip install discussion-helper
```

Chaque extrait ci-dessous suppose ces imports : une section se lit donc seule,
sans chercher à quoi `SilentVoice` était liée.

```python
import asyncio

from discussion_helper import Discussion, Floor, Policy, Responder
from discussion_helper.testing import EchoResponder, ScriptedListener, SilentVoice
```

Deux sections en demandent davantage ; chacune répète sa ligne d'installation
là où elle commence. La section 10 veut les trois paquets frères plus une carte
son, la section 11 veut un serveur web.

```bash
pip install 'discussion-helper[all]'      # entendre, penser, parler, jouer
pip install 'discussion-helper[server]'   # la surface HTTP et sa socket
```

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

## 11. HTTP et un agent qui peut interrompre

```bash
pip install 'discussion-helper[server]'
uvicorn discussion_helper.api:build --factory   # 127.0.0.1:8000, docs sur /docs
```

`discussion_helper.api` est une **fabrique** ASGI, pas un script : il n'existe
pas de `python -m discussion_helper.api` ; lancé ainsi, le module sort en
silence sans avoir rien servi. `discussion-helper-mcp` est l'autre porte — la
même application avec le point d'entrée MCP monté à côté des routes, sur le
port 8090.

Le transport `fake` fait tourner la boucle sans matériel : toute la surface
s'exerce donc hors ligne.

```bash
id=$(curl -s -X POST localhost:8000/sessions \
          -H 'Content-Type: application/json' \
          -d '{"transport":"fake","turns":["bonjour"]}' \
     | python -c 'import sys, json; print(json.load(sys.stdin)["id"])')

curl -s localhost:8000/sessions/$id              # transcription, parole et temps
curl -s -X POST localhost:8000/sessions/$id/interrupt
curl -s -X DELETE localhost:8000/sessions/$id | python -m json.tool
```

```json
{
    "ended": "w--dlTIMyVpJ",
    "utterances": [
        {
            "speaker": "user",
            "text": "bonjour",
            "interrupted": false
        },
        {
            "speaker": "agent",
            "text": "bonjour",
            "interrupted": true
        }
    ],
    "timings": [
        {
            "endpoint_s": 0.0,
            "recognise_s": 0.0,
            "think_s": 0.0,
            "speak_s": 0.0,
            "to_first_audio_s": 0.0,
            "slowest_stage": "think"
        }
    ]
}
```

`"interrupted": true` sur le tour de l'agent, c'est le bouton qui a fait
exactement ce que fait une coupure de parole. À noter : le corps de requête de
`POST /sessions` n'est pas facultatif — sans lui FastAPI répond `422`, puisque
le transport et la politique doivent bien venir de quelque part.
`GET /sessions/{id}/events` donne la même conversation en Server-Sent Events,
pour un appelant qui préfère regarder que sonder.

`POST /turn` prend un seul tour sous forme de texte : c'est la seule façon de
demander directement quelque chose au modèle de la conversation. C'est aussi
la seule route d'ici qui ne soit pas hors ligne : elle réclame `[think]` plus
un modèle sur la machine.

Avec `[mcp]` installé, `discussion-helper-mcp` republie ces mêmes routes comme
outils d'agent — une seule implémentation, si bien que les deux surfaces ne
peuvent pas dériver vers un désaccord. Un agent ne peut pas *tenir* une
conversation (il n'a pas d'oreilles), mais il peut en démarrer une, la
surveiller, prendre un tour et l'**interrompre**. C'est cette dernière capacité
qui justifie la surface : « arrête de parler » est une chose que les gens
disent à un agent ; la faire passer par le même `Voice.stop` que
l'interruption du micro signifie qu'elle s'arrête de la même façon — en jetant
ce qui a été synthétisé plutôt qu'en le laissant s'écouler.

## Ligne de commande

Une seule ligne de commande, `discussion-helper`, bâtie avec click, avec deux
commandes : `rehearse` et `talk`.

```bash
# La boucle, sans matériel. Commencez ici.
discussion-helper rehearse 'bonjour' 'ça va ?'

# Mettre en scène une coupure 200 ms après le début d'une réponse de cinq phrases.
discussion-helper rehearse 'bonjour' --sentences 5 --interrupt-after 0.2

# Le micro.
discussion-helper talk --voice ff_siwis --language fr
discussion-helper talk --no-barge-in          # semi-duplex strict
discussion-helper talk --json                 # lisible par une machine
```

La coupure mise en scène est celle qui vaut d'être lancée :

```
 you: bonjour
  it: bonjour bonjour (2) bonjour (3) (cut off)

turn 1: 0 ms to first audio, slowest stage think
```

Trois phrases ont démarré avant que la coupure n'arrive, parce que la voix
factice lit sans rien coûter ; la troisième est celle qu'elle a coupée, les
deux suivantes n'ayant jamais commencé. Si les cinq apparaissaient, la file
serait en train de s'écouler au lieu d'être jetée.

Toutes les options des deux commandes sont dans
[`skills/discussion-helper/references/cli-reference.md`](https://github.com/warith-harchaoui/discussion-helper/blob/main/skills/discussion-helper/references/cli-reference.md).

## Dépannage

**`rehearse` marche, `talk` non.** C'est exactement le partage que les deux
commandes servent à faire : la boucle va bien. `talk` réclame les paquets
frères ; celui qui manque nomme sa propre ligne d'installation au lieu de
lever une `ImportError` sur un paquet que vous n'avez jamais importé :

```
hearing needs vocal-helper and a microphone. Install them with:
    pip install 'discussion-helper[listen]'
```

`answering needs a local model`, `speaking needs speaker-helper` puis `playing
audio needs a sound card binding` ont la même forme pour `[think]`, `[speak]`
et `[play]`. `GET /health` répond à la même question pour les quatre d'un coup.

**L'agent s'interrompt lui-même au bout d'une syllabe.** Sa propre voix
revient dans son propre micro ; sans annulation d'écho, c'est indiscernable de
vous qui commencez à parler. Montez `--grace` — 0,35 s par défaut, un
haut-parleur en veut davantage — ou passez `--no-barge-in` pour du semi-duplex
strict. Le vrai correctif est l'annulation d'écho acoustique, que ce paquet ne
livre délibérément pas ; KNOWLEDGE.md §4 dit pourquoi.

**C'est lent, la transcription a l'air juste.** Lisez `slowest_stage` avant de
toucher à quoi que ce soit. `think` sur le répondeur local, c'est la génération
*entière* et non un premier jeton : le levier est donc la longueur de la
réponse (`--max-sentences` ou le prompt système) plutôt qu'une machine plus
rapide. `endpoint` désigne au contraire la détection de fin de tour, qui vit
dans `vocal-helper`.

**Le modèle.** Rien ici n'en code un en dur. `LocalResponder` appelle
`best_engine_ai_helper.llm.chat_stream` ; c'est `best-engine-ai-helper` qui
décide quel modèle tient sur cette machine. « Quel modèle est-ce que je fais
tourner » est donc une question pour ce paquet-là, pas pour celui-ci.
