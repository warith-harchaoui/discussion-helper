# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/discussion-helper/blob/main/LANDSCAPE.md)

Outils voisins ou concurrents dans l'espace « tenir une conversation parlée, en
temps réel, là où savoir à qui est le tour compte », comparés à
`discussion-helper`. Les notes vont de ⭐ (1) à ⭐⭐⭐⭐⭐ (5), évaluées
par rapport au travail que `discussion-helper` se donne : une boucle de
conversation **en forme de bibliothèque**, **locale d'abord**, dont le
comportement d'interruption est **juste et observable**, qui se compose avec le
reste de la pile AI Helpers (`vocal-helper`, `speaker-helper`,
`best-engine-ai-helper`). Un projet optimisé pour un tout autre travail — une
plateforme de téléphonie portant dix mille appels simultanés, par exemple —
n'est pas pénalisé ; la note reflète seulement l'adéquation à *cette* niche.

La dernière colonne est là exprès. `discussion-helper` y obtient ⭐ et serait
un mauvais choix pour un centre d'appels. Une table où le meneur gagne toutes
les colonnes est un tableau d'honneur, pas un paysage.

## En un coup d'œil

<!-- TABLE:START -->
| Conversation Parlée | Fonctionne en local | Interruption qui jette l'audio en attente | Décomposition de latence par étape | Forme bibliothèque | Testable sans matériel | Parties interchangeables | Téléphonie et montée en charge |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **discussion-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| LiveKit Agents | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pipecat | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenAI Realtime API | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Vocode | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Vapi | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Amazon Lex | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Rasa | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| speech_recognition + pyttsx3 | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/discussion-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 7 critères : à lire comme une forme, pas comme un classement. « discussion-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal : Fiabilité ↔ Structure** et **Vertical : Adaptabilité ↔ Efficacité**.

L'organisation de ces solutions selon l'axe horizontal révèle une tension entre leur capacité à fonctionner de manière autonome et leur robustesse architecturale. Les options positionnées à gauche, comme Vapi ou Amazon Lex, privilégient une certaine indépendance et une gestion des imprévus, au prix d'une structure potentiellement moins rigide. À l'inverse, celles à droite, menées par discussion-helper et speech_recognition + pyttsx3, se distinguent par une architecture plus définie et une meilleure organisation interne, même si cela peut les rendre moins flexibles face à des situations imprévisibles.

L'axe vertical met en lumière un compromis entre la capacité à s'adapter à des environnements variés et la performance globale. Les solutions situées en haut, discussion-helper et LiveKit Agents, excellent dans leur domaine, optimisant l'utilisation des ressources et minimisant les délais. En revanche, celles qui se trouvent en bas, comme OpenAI Realtime API ou Rasa, semblent accorder plus d'importance à la flexibilité et à la capacité d'intégration, même si cela se fait au détriment de l'efficacité brute.

On observe un regroupement intéressant dans le coin supérieur droit, où discussion-helper et Pipecat se positionnent. Ils partagent une forte efficacité et une structure bien définie, ce qui les rend particulièrement adaptés aux applications nécessitant à la fois performance et organisation. À l'opposé, le coin inférieur gauche rassemble un ensemble d'options – OpenAI Realtime API, Vapi, Amazon Lex – qui misent sur la fiabilité et l'adaptabilité, même si cela implique un certain compromis sur la performance. Enfin, le coin inférieur droit voit se regrouper Vocode, Rasa et speech_recognition + pyttsx3, qui, bien que structurés, privilégient une certaine adaptabilité.
<!-- FIGURE:END -->

## Positionnement

Trois paquets faisaient déjà le travail avant celui-ci. `vocal-helper` entend,
`speaker-helper` parle, un modèle local répond. **Aucun ne sait à qui est le
tour.** Ce manque — ni entendre ni parler — constitue tout
`discussion-helper`. Il ne fait délibérément *aucune* détection de tour qui lui
soit propre : `vocal-helper` embarque Silero VAD ainsi qu'une étape de fin de
tour sémantique calquée sur le `turn-detector` de LiveKit ; réimplémenter
l'une ou l'autre ici lui donnerait deux propriétaires.

Ce qu'il ajoute, c'est le tour de parole : quatre états, un seul détenteur à la
fois, plus la règle que `THINKING` s'interrompt autrement que `SPEAKING` — penser
peut s'abandonner en silence, parler doit s'*arrêter* et l'audio en attente
être jeté. Cette dernière clause est le vrai point distinctif de la table
ci-dessus. Une réponse est synthétisée en avance sur la lecture, donc une
interruption trouve toujours de l'audio fabriqué et pas encore entendu ; le
jouer quand même — parce qu'il existe, parce qu'il a été payé — est exactement
ce qui fait qu'un agent paraît sourd. Vider la file au lieu de la jeter est la
manière la plus courante de se tromper ici ; elle est invisible dans une
transcription : le texte d'une réponse interrompue a l'air complet.

Le deuxième point distinctif : rien de tout cela ne réclame une pièce.
`Listener`, `Responder` et `Voice` sont des protocoles structurels livrés avec
leurs doublures, si bien que la logique du tour de parole, l'interruption et la
comptabilité de latence tournent en intégration continue sans micro, sans
modèle ni carte son. Le comportement le plus difficile à réussir dans un agent
vocal est aussi le plus difficile à *entendre* : l'audio s'est-il vraiment
arrêté, la file a-t-elle été jetée, le tour est-il revenu. Un test à voix réelle
n'observe rien de cela.

Troisièmement, la décomposition de latence se fait par étape plutôt qu'en
total ; elle nomme le `slowest_stage`. Un chiffre unique dit qu'une
conversation paraît lente sans rien dire du pourquoi. Le temps jusqu'au premier
son et la lecture sont rapportés séparément, car les confondre fait paraître un
moteur rapide lisant une longue phrase plus lent qu'un moteur lent lisant une
phrase courte.

Chaque alternative porte des nuances que les étoiles compriment. **LiveKit
Agents** est l'implémentation de référence de cette catégorie et fait mieux que
ce paquet sur presque tout ce qui n'est pas ci-dessus : transport WebRTC,
téléphonie SIP, un détecteur de tour *entraîné* plutôt qu'un seuil de VAD, et
une vraie montée en charge horizontale. Il a toutefois la forme d'un cadriciel
— on déploie un ouvrier, on n'importe pas une boucle — et son chemin
confortable passe par des fournisseurs en nuage. **Pipecat** est aussi capable
et plus riche en intégrations, bâti comme un pipeline de processeurs de trames ;
il accepte les modèles locaux mais l'unité de composition reste le pipeline,
pas un protocole qu'on implémente en une classe. **L'API Realtime d'OpenAI** a
le meilleur comportement d'interruption de la table ainsi que la plus faible
latence, parce que le VAD, le modèle et la voix forment un seul système côté
serveur — et elle est aussi entièrement en nuage, n'offre presque aucune
décomposition du temps passé ; elle ne s'exerce pas sans l'API. **Vocode** est le
plus proche en forme de ce paquet, libre et Python d'abord, avec la téléphonie
via Twilio, mais son interruption et son observabilité sont plus minces.
**Vapi** est une plateforme hébergée : excellent délai jusqu'à la première
démonstration, de la configuration plutôt que du code. **Amazon Lex** relève
d'une génération antérieure — intentions et créneaux, téléphonie d'abord via
Connect, interruption en réglage plutôt qu'en conception. **Rasa** fait de la
gestion de dialogue, texte d'abord ; elle le fait vraiment bien ; la voix y est un
connecteur ; le tour de parole n'est pas son problème.
**`speech_recognition` + `pyttsx3`** est la base bricolée que tout le monde
essaie en premier : locale, trivialement en forme de bibliothèque, bloquante
de bout en bout, donc l'utilisateur ne peut pas interrompre du tout.

## Quand choisir quoi

- **`discussion-helper`** : une personne, une machine, une conversation qui
  doit s'arrêter quand elle coupe — et l'envie de lire pourquoi c'était lent.
  Se compose avec le reste de la suite AI Helpers.
- **LiveKit Agents** : il faut WebRTC ou la téléphonie, beaucoup de sessions
  simultanées, voire un détecteur de tour entraîné plutôt qu'un seuil de VAD. La
  bonne réponse à l'échelle.
- **Pipecat** : on veut un pipeline riche avec beaucoup d'intégrations prêtes
  et composer des processeurs ne dérange pas.
- **API Realtime d'OpenAI** : la latence la plus basse l'emporte et le nuage
  est acceptable. Parole à parole en un saut, interruption gérée côté serveur.
- **Vocode** : un agent vocal libre en Python avec téléphonie Twilio, sans
  besoin de la comptabilité du tour de parole.
- **Vapi** : on veut un agent vocal qui marche cet après-midi et on préfère
  configurer que construire.
- **Amazon Lex** : on est déjà dans AWS Connect et on pense en intentions et
  créneaux.
- **Rasa** : la partie difficile est la *gestion de dialogue*, pas le tour de
  parole ; l'essentiel du trafic est du texte.
- **`speech_recognition` + `pyttsx3`** : une démonstration où personne
  n'interrompra.

## Sources et date de relevé

**Relevé le 27/10/2026.** Les étoiles sont un jugement d'adéquation à *cette*
niche — une boucle de conversation en forme de bibliothèque, locale d'abord,
dont le comportement d'interruption est juste et observable — pas un résultat
de banc d'essai. Elles ont été attribuées en lisant la documentation de chaque
projet, puis son code quand il est public. Rien de ce tableau n'a été
chronométré ici : aucun chiffre de latence, de débit ni de version n'est donc
cité contre le logiciel de quelqu'un d'autre. Ce sont exactement les
affirmations qui pourrissent jusqu'à devenir fausses au sujet d'autrui.

| Projet | Lu dans |
|---|---|
| LiveKit Agents | [docs.livekit.io/agents](https://docs.livekit.io/agents/) · [détecteur de tour](https://docs.livekit.io/agents/build/turns/turn-detector/) |
| Pipecat | [docs.pipecat.ai](https://docs.pipecat.ai/) |
| API Realtime d'OpenAI | [platform.openai.com — Realtime](https://platform.openai.com/docs/guides/realtime) |
| Vocode | [vocodedev/vocode-core](https://github.com/vocodedev/vocode-core) |
| Vapi | [docs.vapi.ai](https://docs.vapi.ai/) |
| Amazon Lex | [docs.aws.amazon.com/lex](https://docs.aws.amazon.com/lex/) |
| Rasa | [rasa.com/docs](https://rasa.com/docs/) |
| `speech_recognition` + `pyttsx3` | [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) · [pyttsx3](https://pypi.org/project/pyttsx3/) |

La ligne de `discussion-helper` se lit dans ce dépôt plutôt qu'elle ne
s'affirme. *Interruption qui jette l'audio en attente*, c'est
`tests/test_the_floor.py::test_what_was_queued_and_not_heard_is_discarded` :
il met en scène une coupure dans une réponse de cinq phrases puis exige que la
phrase atteinte compte comme commencée et non comme dite, les quatre suivantes
ne démarrant jamais. Son voisin `test_the_interruption_is_fast` tient l'arrêt
complet sous 150 ms face à une phrase d'une seconde. *Testable sans matériel*,
c'est la suite de tests elle-même, qui tourne sans micro, sans modèle ni carte
son. *Décomposition de latence par étape*, c'est `TurnTiming.as_dict()` — les
six mêmes champs que rendent le `--json` de la ligne de commande et le flux
d'événements HTTP. Le ⭐ en *Téléphonie et montée en charge* se mesure dans le
seul sens disponible : il n'y a ici de code ni pour l'une ni pour l'autre.

Les chiffres publiés face auxquels ce paquet a été conçu — le budget de 800 ms,
la barre de 150 ms pour l'interruption, la baisse rapportée de 39 % des fausses
interruptions quand la fin de tour sémantique est fusionnée avec la détection
d'activité vocale — appartiennent à d'autres ; chacun est cité individuellement
dans
[KNOWLEDGE.md § Sources](https://github.com/warith-harchaoui/discussion-helper/blob/main/KNOWLEDGE.md#sources).
Ils ne sont pas refaits ici.
