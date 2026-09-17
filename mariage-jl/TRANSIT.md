# Copie de transit — à supprimer

Ce dossier n'appartient pas au projet CAO-LEGO. C'est la copie de travail du
projet **mariage-jl** (l'application du mariage de Julien & Lauriane), conservée
ici uniquement parce que :

1. la décision du 17/09/2026 est de lui donner un **dépôt dédié** ;
2. l'App GitHub de la session n'a pas le droit de créer un dépôt (HTTP 403) ;
3. le conteneur de travail est éphémère : sans copie poussée, tout serait perdu.

**Pour clore le transit** : créer le dépôt privé `mariage-jl` sur GitHub (ou
donner accès à cette session), y pousser cette copie, puis supprimer ce dossier
de CAO-LEGO en une commande :

```bash
git rm -r --cached mariage-jl && rm -rf mariage-jl && git commit -m "Fin du transit mariage-jl"
```

L'historique du projet (V0 puis V1) vit dans le dépôt local
`/home/user/mariage-jl` de la session ; cette copie en est le contenu à plat.
