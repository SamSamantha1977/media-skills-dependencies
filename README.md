# Media Skills for OpenAI (SamSamantha1977)

Deux skills Python 3.11+ independantes :

- Upscayl-Image : resize et compress avec Pillow ; enhance lorsque Upscayl NCNN et ses modeles sont disponibles.
- Video2X-Video : resize, interpolate via FFmpeg minterpolate sans RIFE, compress ; enhance avec Video2X RealESRGAN et GPU compatible.

## Installer les skills
Archives legeres dist/upscayl-image.zip et dist/video2x-video.zip, moins de 50 Mo.
Elles ciblent le format Skills API OpenAI ; ChatGPT n'assure pas l'acces reseau, GPU ou l'installation de binaires.
Scripts dans skills/<nom>/scripts/run.py. Python 3.11+.
Verifier via python scripts/dependencies.py --check.

## Binaires lourds (non publies)
Les paquets FFmpeg/FFprobe, Upscayl NCNN et Video2X NCNN Windows sont prepares hors du depot.
docs/native-asset-checksums.json contient leurs SHA-256.
Aucune URL de telechargement n'est activee dans les manifests tant que les assets ne sont pas publies et leurs licences verifiees.

## Documentation
Consulter SKILL.md et references/RUNTIME.md de chaque skill, et docs/LEGAL_REVIEW.md.
Ne pas ajouter de jeton GitHub aux sources.

Ce depot est independant de SamSamantha1977/Cassandre et n'en modifie pas les releases.
