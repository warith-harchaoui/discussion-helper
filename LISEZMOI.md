# Discussion Helper

[🇫🇷](https://github.com/warith-harchaoui/discussion-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/discussion-helper/blob/main/README.md)

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Discussion Helper` fait partie d'une collection de bibliothèques appelée
`AI Helpers`, développée pour construire de l'intelligence artificielle.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

**Tenir une conversation parlée au micro : écouter, répondre, parler — et se
taire à l'instant où l'on vous coupe.**

`vocal-helper` entend. `speaker-helper` parle. Un modèle local répond. Aucun
des trois ne sait à qui est le tour. Ce paquet est la boucle entre les trois,
et les trois questions qu'elle doit trancher :

- **Qui a la parole.** Une seule partie à la fois. La plupart des ratés d'un
  agent vocal sont deux parties qui croient l'avoir — l'agent qui parle
  par-dessus l'utilisateur est le cas visible ; les deux qui se taisent est
  celui que personne ne remarque avant de réécouter l'enregistrement.
- **Ce qui se passe quand on vous coupe.** Moins de **150 ms** entre la
  première syllabe et le silence de l'agent, et l'audio déjà synthétisé mais
  pas encore entendu est **jeté**, pas vidé. Le faire jouer parce qu'il
  existe, c'est ce qui donne à un agent l'air d'être sourd.
- **Où est passée la latence.** Un total dit qu'une conversation traîne et
  rien sur la raison. Chaque échange rend sa décomposition — détection de fin
  de tour, reconnaissance, premier jeton, premier son — et nomme l'étape à
  corriger.

## La promesse

**Local d'abord.** Le micro, la reconnaissance, le modèle et la voix tournent
sur votre machine. Aucun son n'en sort, pas de compte, pas de facturation à la
minute.

**Testable sans pièce.** Les trois parties sont des protocoles : toute la
boucle tourne en intégration continue sans micro, sans modèle et sans carte
son. Ce n'est pas de la coquetterie — la gestion de l'interruption est
précisément ce qu'une vraie pièce rend impossible à vérifier. On ne peut pas
*entendre* si la file d'attente a bien été jetée.

## Installation

```bash
pip install 'discussion-helper[all]'
speaker-helper install-voice --engine kokoro   # les poids de la voix, une fois
```

Sous Linux et macOS il faut aussi `espeak-ng` (`apt install espeak-ng`,
`brew install espeak-ng`).

## L'essayer sans rien installer

```bash
pip install discussion-helper
discussion-helper rehearse "bonjour" "comment ça va ?"
```

`rehearse` fait tourner **la même boucle** avec le micro, le modèle et le
haut-parleur remplacés par des doublures. Quand un agent vocal se comporte
mal, la première question est toujours « est-ce la boucle ou est-ce la
pièce ? », et ceci y répond en une seconde :

```bash
discussion-helper rehearse "dis-moi tout" --sentences 6 --interrupt-after 0.25 --grace 0
```

```
 you: dis-moi tout
  it: dis-moi tout dis-moi tout (2) (cut off)
```

## Lui parler

```bash
discussion-helper talk --voice ff_siwis
discussion-helper talk --no-barge-in        # semi-duplex strict
discussion-helper talk --json               # transcription + latences
```

## En bibliothèque

```python
import asyncio
from discussion_helper import Discussion, Policy
from discussion_helper.adapters import VocalListener, LocalResponder, SpeakerVoice


async def main():
    async with Discussion(
        VocalListener(language="fr"),
        LocalResponder(),
        SpeakerVoice(voice="ff_siwis"),
        Policy(barge_in_grace_s=0.35),
    ) as talk:
        conversation = await talk.run()

    for turn in conversation.utterances:
        print(turn.speaker, turn.text)
    print(conversation.timings[0].as_dict())


asyncio.run(main())
```

Apportez vos propres pièces en implémentant `Listener`, `Responder` ou
`Voice` — un moteur de reconnaissance distant, un modèle scripté pour une
démo, une ligne téléphonique au lieu d'un haut-parleur. Chacune est une seule
classe, et la boucle ne change pas.

## Sur HTTP, et sur une socket

Une conversation ne tient pas dans une requête — elle n'a pas de réponse
unique et dure des minutes — alors la surface HTTP est une session qu'on crée,
un flux qu'on suit et un bouton qu'on presse :

```bash
pip install 'discussion-helper[server]'
discussion-helper-mcp            # ou : uvicorn discussion_helper.api:build --factory
```

| Route | Ce que c'est |
|---|---|
| `GET /health` | si chacune des trois parties pourrait tourner ici, et ce qui manque |
| `POST /sessions` | en démarrer une ; rend un identifiant immédiatement |
| `GET /sessions` | toutes les conversations que ce processus tient |
| `GET /sessions/{id}` | la transcription, la parole et les temps, en l'état |
| `GET /sessions/{id}/events` | la suivre — parole, tours, latence, au fil de l'eau |
| `POST /sessions/{id}/say` | pousser un tour utilisateur en texte, pour une session distante |
| `POST /sessions/{id}/interrupt` | arrêter l'agent, par le même chemin qu'une coupure de parole |
| `DELETE /sessions/{id}` | la terminer, et récupérer ce qui a été dit |
| `WS /sessions/{id}/audio` | **le micro à l'autre bout** |
| `POST /turn` | un échange, sans audio — la forme qu'un agent peut utiliser |
| `/mcp` | les mêmes routes en outils d'agent |

La WebSocket porte de l'audio réel dans les deux sens : le client envoie du
PCM et des trames de contrôle, le serveur renvoie des événements et du WAV.
C'est ainsi que fonctionne tout agent vocal hébergé, et cela veut dire que le
navigateur peut tenir le micro pendant que ce bout tient le modèle. Deux
devoirs incombent au client et ne sont pas facultatifs — envoyer
`{"type":"speaking"}` à la **première syllabe** pour qu'une coupure puisse
voyager, et **jeter** l'audio tamponné sur `{"kind":"stop"}`. Un client qui
joue son tampon jusqu'au bout reproduit, à l'autre bout, exactement la surdité
que l'arrêter ici devait empêcher.

## Dans un conteneur

```bash
docker compose up -d
curl -s localhost:8090/health
```

L'image sert le transport **distant** — c'est l'appelant qui tient le micro et
envoie les trames — et c'est la moitié de ce paquet qu'un conteneur peut
honnêtement faire tourner. Elle n'ouvre **pas** de micro : `--transport local`
lit la carte son de la machine, et un conteneur n'en a pas. En passer une, ce
sont des `--device /dev/snd` sous Linux et rien du tout sous macOS — un
arrangement par machine, pas une image. L'extra `listen` est donc
volontairement absent, et le refus arrive à l'installation plutôt qu'au
premier appel.

Le port est lié à la boucle locale, et la raison est aussi dans
`discussion-helper-mcp --help` : ce serveur peut ouvrir un micro. Un seul
worker, également délibéré — le moteur de voix charge son graphe ONNX une fois
par processus et un second en paierait sa propre copie, et les sessions ont un
état.

## À lire avant de régler quoi que ce soit

**[KNOWLEDGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md)** est le carnet de conception : le budget de
800 ms et où il part vraiment, pourquoi un seuil de silence n'est pas une
détection de fin de tour, les deux fautes que tout le monde commet une fois
avec l'interruption, pourquoi on découpe les réponses à la phrase et non au
jeton, et pourquoi l'écho acoustique décide de vos réglages par défaut.

En bref : un agent vocal a environ 800 ms avant que la conversation paraisse
cassée, la plus grosse ligne de ce budget est la détection de fin de tour et
non le modèle, et la propre voix de l'agent qui revient dans son propre micro
ressemble exactement à l'utilisateur qui parle.

## Auteur

[Warith HARCHAOUI](https://warith-harchaoui.github.io/) —
warithmetics@deraison.ai

## Licence

BSD-3-Clause. Voir [LICENSE](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE).
