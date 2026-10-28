# Discussion Helper

[🇫🇷](https://github.com/warith-harchaoui/discussion-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/discussion-helper/blob/main/README.md)

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Discussion Helper` fait partie d'une collection de bibliothèques appelée
`AI Helpers`, développée pour construire de l'intelligence artificielle.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

**Tenir une conversation parlée au micro : écouter, répondre, parler — et se
taire à l'instant où l'on vous coupe.**

`vocal-helper` entend. `speaker-helper` parle. Un modèle local répond, choisi
par `best-engine-ai-helper`, qui mesure la machine : aucun nom de modèle n'est
écrit ici. Aucun des trois ne sait à qui est le tour. Ce paquet est la boucle
entre eux, plus les trois questions qu'elle doit trancher :

- **Qui a la parole.** Une seule partie à la fois. La plupart des ratés d'un
  agent vocal sont deux parties qui croient l'avoir — l'agent qui parle
  par-dessus l'utilisateur est le cas visible ; les deux qui se taisent est
  celui que personne ne remarque avant de réécouter l'enregistrement.
- **Ce qui se passe quand on vous coupe.** Moins de **150 ms** entre la
  première syllabe et le silence de l'agent ; l'audio déjà synthétisé mais
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

## Comment ça marche

![Comment discussion-helper fonctionne : la boucle qui écoute, répond puis parle — et s'arrête dès que vous coupez](https://raw.githubusercontent.com/warith-harchaoui/discussion-helper/main/assets/diagrams/comment-ca-marche.png)

## Installation

```bash
pip install 'discussion-helper[all]'
speaker-helper install-voice --engine kokoro   # les poids de la voix, une fois
```

Sous Linux et macOS il faut aussi `espeak-ng` (`apt install espeak-ng`,
`brew install espeak-ng`).

Chaque moitié s'installe seule si vous n'en voulez qu'une partie : `[listen]`,
`[think]`, `[speak]`, `[play]`.

## Prise en main rapide

La boucle tourne sur une installation nue — sans modèle, sans micro, sans
carte son. Les trois parties sont des protocoles et le paquet livre une
doublure connue-bonne de chacune : il y a donc une conversation à regarder
avant d'avoir téléchargé le moindre poids.

```bash
pip install discussion-helper
discussion-helper rehearse 'bonjour' 'ça va ?'
```

```
 you: bonjour
  it: bonjour bonjour (2) bonjour (3)
 you: ça va ?
  it: ça va ? ça va ? (2) ça va ? (3)

turn 1: 0 ms to first audio, slowest stage think
turn 2: 0 ms to first audio, slowest stage think
```

Deux échanges, le tour de parole qui change quatre fois de main, la latence
rapportée par tour avec l'étape à corriger nommée. Puis, les extras ci-dessus
installés, la même boucle au micro :

```bash
discussion-helper talk
```

Parlez : il répond. Coupez-le : il se tait. `--json` remplace la prose par la
transcription et la décomposition de latence en JSON lisible par une machine ;
[En bibliothèque](#en-bibliothèque) donne la même conversation pilotée depuis
Python.

## Est-ce la boucle ou est-ce la pièce ?

C'est la première question qu'un agent vocal fautif soulève ; sans quelque
chose comme `rehearse`, la seule façon de la poser est de changer un réglage
puis de réécouter. La commande fait tourner **la même boucle** avec le micro,
le modèle et le haut-parleur remplacés par des doublures : elle sait donc
aussi mettre l'interruption en scène.

```bash
discussion-helper rehearse "dis-moi tout" --sentences 6 --interrupt-after 0.25 --grace 0
```

```
 you: dis-moi tout
  it: dis-moi tout dis-moi tout (2) (cut off)

turn 1: 0 ms to first audio, slowest stage think
```

`(cut off)` est la boucle qui dit que la phrase sur laquelle elle a été coupée
ne compte **pas** comme dite. Si les six apparaissaient, la file serait en
train de s'écouler au lieu d'être jetée — précisément ce qui donne à un agent
l'air d'être sourd.

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
classe ; la boucle ne change pas.

## Sur HTTP et sur une socket

Une conversation ne tient pas dans une requête — elle n'a pas de réponse
unique et dure des minutes — alors la surface HTTP est une session qu'on crée,
un flux qu'on suit et un bouton qu'on presse :

```bash
pip install 'discussion-helper[server]'
discussion-helper-mcp            # ou : uvicorn discussion_helper.api:build --factory
```

| Route | Ce que c'est |
|---|---|
| `GET /health` | si chacune des trois parties pourrait tourner ici, plus ce qui manque |
| `POST /sessions` | en démarrer une ; rend un identifiant immédiatement |
| `GET /sessions` | toutes les conversations que ce processus tient |
| `GET /sessions/{id}` | la transcription, la parole et les temps, en l'état |
| `GET /sessions/{id}/events` | la suivre — parole, tours, latence, au fil de l'eau |
| `POST /sessions/{id}/say` | pousser un tour utilisateur en texte, pour une session distante |
| `POST /sessions/{id}/interrupt` | arrêter l'agent, par le même chemin qu'une coupure de parole |
| `DELETE /sessions/{id}` | la terminer, puis récupérer ce qui a été dit |
| `WS /sessions/{id}/audio` | **le micro à l'autre bout** |
| `POST /turn` | un échange, sans audio — la forme qu'un agent peut utiliser |
| `/mcp` | les mêmes routes en outils d'agent |

La WebSocket porte de l'audio réel dans les deux sens : le client envoie du
PCM et des trames de contrôle, le serveur renvoie des événements et du WAV.
C'est ainsi que fonctionne tout agent vocal hébergé ; cela veut dire que le
navigateur peut tenir le micro pendant que ce bout tient le modèle. Deux
devoirs incombent au client et ne sont pas facultatifs — envoyer
`{"type":"speaking"}` à la **première syllabe** pour qu'une coupure puisse
voyager, puis **jeter** l'audio tamponné sur `{"kind":"stop"}`. Un client qui
joue son tampon jusqu'au bout reproduit, à l'autre bout, exactement la surdité
que l'arrêter ici devait empêcher.

### Dans un conteneur

```bash
docker compose up -d
curl -s localhost:8090/health
```

L'image sert le transport **distant** — c'est l'appelant qui tient le micro et
envoie les trames — et c'est la moitié de ce paquet qu'un conteneur peut
honnêtement faire tourner. Elle n'ouvre **pas** de micro : `--transport local`
lit la carte son de la machine ; un conteneur n'en a pas. En passer une, ce
sont des `--device /dev/snd` sous Linux et rien du tout sous macOS — un
arrangement par machine, pas une image. L'extra `listen` est donc
volontairement absent ; le refus arrive à l'installation plutôt qu'au
premier appel.

Le port est lié à la boucle locale ; la raison est aussi dans
`discussion-helper-mcp --help` : ce serveur peut ouvrir un micro. Un seul
worker, également délibéré — le moteur de voix charge son graphe ONNX une fois
par processus et un second en paierait sa propre copie ; les sessions ont un
état.

## À lire avant de régler quoi que ce soit

**[KNOWLEDGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md)** est le carnet de conception : le budget de
800 ms et où il part vraiment, pourquoi un seuil de silence n'est pas une
détection de fin de tour, les deux fautes que tout le monde commet une fois
avec l'interruption, pourquoi on découpe les réponses à la phrase et non au
jeton, enfin pourquoi l'écho acoustique décide de vos réglages par défaut.

En bref : un agent vocal a environ 800 ms avant que la conversation paraisse
cassée, la plus grosse ligne de ce budget est la détection de fin de tour et
non le modèle ; la propre voix de l'agent qui revient dans son propre micro
ressemble exactement à l'utilisateur qui parle.

## Le reste de la documentation

| Fichier | Ce qu'il contient |
|---|---|
| **[EXEMPLES.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/EXEMPLES.md)** | Un livre de recettes. Tout ce qui précède la section où arrive le vrai micro tourne sur une installation nue — sans micro, sans modèle ni carte son — parce que les parties sont des protocoles livrés avec leurs doublures. |
| **[KNOWLEDGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md)** | Le carnet de conception, ci-dessus. |
| **[PAYSAGE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/PAYSAGE.md)** / **[LANDSCAPE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/LANDSCAPE.md)** | La place de ce paquet face à LiveKit Agents, Pipecat, l'API Realtime d'OpenAI ainsi que six autres, avec une carte de positionnement. Il obtient ⭐ en téléphonie et montée en charge : c'est la réponse honnête. |
| **[TRIGGERS.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/TRIGGERS.md)** | Le catalogue exhaustif de ce qui doit — et ne doit pas — mener à ce helper. Recopié dans la compétence d'agent, avec une barrière qui échoue dès que les deux divergent. |
| **[CHANGELOG.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/CHANGELOG.md)** | Ce qui a changé et pourquoi. |

## En quoi il diffère de ses voisins

| Vous avez | Prenez |
|---|---|
| Un enregistrement que quelqu'un veut en texte | [`vocal-helper`](https://github.com/warith-harchaoui/vocal-helper) |
| Du texte que quelqu'un veut en parole | [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper) |
| Une caméra ou un micro en direct, en trames | [`capture-helper`](https://github.com/warith-harchaoui/capture-helper) |
| Une question qu'un modèle local doit trancher | [`best-engine-ai-helper`](https://github.com/warith-harchaoui/best-engine-ai-helper) |
| **Une conversation à tenir** | celui-ci |

La ligne de partage qui évite la plupart des erreurs : **lire quelque chose à
voix haute** relève de `speaker-helper`, même si c'est long. Ce paquet ne sert
qu'au cas où quelqu'un va *répondre*, là où la machine doit s'arrêter quand
il le fait.

## Ce qui est volontairement absent

Pas de mot de réveil, pas de diarisation, pas de téléphonie, pas d'annulation
d'écho acoustique, aucune détection de tour non plus — cette dernière vit dans
`vocal-helper`, qui embarque Silero VAD ainsi qu'une étape de fin de tour
sémantique. La réimplémenter ici lui donnerait deux propriétaires. KNOWLEDGE.md
§10 détaille chacun de ces points.

## Auteur

[Warith HARCHAOUI](https://warith-harchaoui.github.io/) —
warithmetics@deraison.ai

## Licence

BSD-3-Clause. Voir [LICENSE](https://github.com/warith-harchaoui/discussion-helper/blob/main/LICENSE).
