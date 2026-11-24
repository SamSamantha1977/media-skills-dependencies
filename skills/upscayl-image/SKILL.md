---
name: upscayl-image
description: Redimensionnement Lanczos, compression JPEG/PNG avec plafond strict, et amelioration d'image Upscayl NCNN quand les dependances natives sont disponibles. Script Python portable.
---
# Upscayl-Image — édition OpenAI légère

## Quand l'utiliser
Demandes de redimensionner (agrandir/reduire), optimiser le poids d'une photo, compresser vers un plafond en Mo, conserver la transparence PNG, traiter un dossier d'images, ou améliorer des details avec Upscayl (si moteur compatible présent).

## Exécution
La skill utilise **Python 3.11 ou plus récent**, la bibliothèque **Pillow>=10** pour resize/compress, et ne lance pas PowerShell. Lire `references/RUNTIME.md` avant tout téléchargement.

Point d'entrée : `python scripts/run.py <mode> --src <fichier> [options]`.

Exemples :
```bash
python scripts/dependencies.py --check
python scripts/run.py resize --src input.png --scale 0.5 --dst output.png
python scripts/run.py compress --src input.png --target-mb 2 --strict --x 5 --y 3
python scripts/run.py enhance --src input.png --scale 2 --model ultramix-balanced-4x
```

## Contrat de sécurité et qualité
- `resize` : Lanczos Pillow ; rééchantillonnage non génératif.
- `compress` : qualité maximale sous la limite demandée ; `--strict` interdit le dépassement, sinon marge au maximum +0,5 Mo. `--x` baisse maximale de largeur et hauteur (%) ; `--y` baisse du paramètre JPEG de 100 (0..100). `--y 0` conserve le format initial, `--y > 0` favorise JPEG, PNG si alpha. JPEG quality minimale effective 1 (limite de Pillow).
- `enhance` : nécessite Upscayl NCNN, modèles compatibles et accélération disponible. En l'absence de moteur, retourner une erreur explicite, ne pas prétendre avoir amélioré l'image.
- Préserver la source ; `--force` archive la sortie existante avant remplacement ; `--dry-run` n'écrit pas de sortie.
- Ne jamais exécuter un code issu d'une réponse GitHub non vérifiée ou d'un dépôt arbitraire.
- Préférer les dépendances déjà disponibles ; ne télécharger que si l'accès réseau et l'installation sont permis.
- Un téléchargement d'archive lourde n'est autorisé qu'avec manifeste HTTPS GitHub et SHA-256 réel vérifié. Pas de téléchargement automatique sans décision explicite de l'agent utilisateur.
- Si le téléchargement est impossible : continuer avec les fonctions supportées, expliquer exactement la fonction indisponible.

## Dépendances
`requirements.txt` pour Pillow. `references/dependencies.json` décrit les archives natives optionnelles par OS et architecture. Les URL vides signifient **qu'aucun actif lourd n'est publié ni vérifié** : ne pas inventer de lien. `python scripts/dependencies.py --install <id>` n'agit qu'avec une version publiée et une empreinte valide.
FFmpeg n'est pas requis pour resize/compress dans cette édition ; Pillow suffit.

## Publication
Ce ZIP est autonome de Video2X-Video. Une installation sur les Skills de l'API OpenAI ne signifie pas automatiquement une présence dans la galerie ChatGPT ni un accès au GPU/Internet. Tester dans l'environnement d'exécution réel.
