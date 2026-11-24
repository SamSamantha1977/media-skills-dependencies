# Verification avant publication des archives natives

Ne pas publier d'archives lourdes avant revue :
1. Licence de FFmpeg et codecs du build (GPL selon options), notices et sources correspondantes si requises.
2. Licences Upscayl NCNN, bibliotheques, chaque modele IA et sources attribuees.
3. Licences Video2X, Vulkan/NCNN, DLL et modeles RealESRGAN.
4. Verification des elements tiers non redistribuables.
5. Tests depuis l'archive re-extraite sur Windows x64, puis versions Linux/macOS adaptees.
6. Publication en GitHub Releases avec SHA256 et URL reelles, puis reconstruction des deux ZIP.
Les scripts legers originaux et les binaires tiers n'ont pas necessairement la meme licence.
