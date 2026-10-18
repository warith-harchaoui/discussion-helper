# Discussion Helper

[🇫🇷](https://github.com/warith-harchaoui/discussion-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/discussion-helper/blob/main/README.md)

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

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

## À lire avant de régler quoi que ce soit

**[KNOWLEDGE.md](KNOWLEDGE.md)** est le carnet de conception : le budget de
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

BSD-3-Clause. Voir [LICENSE](LICENSE).
